"""Tests for replay engine and integrity verification."""


def test_create_replay(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    decision_id = r.json()["decision_id"]
    
    r = client.post("/v1/replays", json={
        "decision_id": decision_id,
        "overrides": {"prompt": {"template": "support_v2"}},
        "triggered_by": "test"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["replay_id"].startswith("rep_")
    assert data["execution_status"] == "completed"
    assert data["execution_mode"] == "simulated"
    assert data["output_changed"] is True


def test_replay_no_overrides(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    decision_id = r.json()["decision_id"]
    
    r = client.post("/v1/replays", json={"decision_id": decision_id})
    assert r.status_code == 200
    assert r.json()["output_changed"] is False


def test_get_replay(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    decision_id = r.json()["decision_id"]
    
    r = client.post("/v1/replays", json={"decision_id": decision_id})
    replay_id = r.json()["replay_id"]
    
    r = client.get(f"/v1/replays/{replay_id}")
    assert r.status_code == 200
    assert r.json()["replay_id"] == replay_id


def test_compare(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    decision_id = r.json()["decision_id"]
    
    r = client.post("/v1/replays", json={
        "decision_id": decision_id,
        "overrides": {"prompt": {"template": "support_v2"}}
    })
    replay_id = r.json()["replay_id"]
    
    r = client.get(f"/v1/decisions/{decision_id}/compare/{replay_id}")
    assert r.status_code == 200
    assert r.json()["output_changed"] is True


def test_replay_not_found(client):
    r = client.post("/v1/replays", json={"decision_id": "dec_doesnotexist"})
    assert r.status_code == 404


# ================================================================
# Integrity Tests
# ================================================================

def test_integrity_empty_ledger(client):
    r = client.get("/v1/integrity/verify")
    assert r.status_code == 200
    assert r.json()["integrity"]["valid"] is True
    assert r.json()["integrity"]["total"] == 0


def test_integrity_valid_chain(client, sample_decision):
    client.post("/v1/decisions", json=sample_decision)
    client.post("/v1/decisions", json=sample_decision)
    client.post("/v1/decisions", json=sample_decision)
    
    r = client.get("/v1/integrity/verify")
    assert r.status_code == 200
    integrity = r.json()["integrity"]
    assert integrity["valid"] is True
    assert integrity["total"] == 3


def test_integrity_filter_by_service(client, sample_decision):
    client.post("/v1/decisions", json=sample_decision)
    other = {**sample_decision, "service_name": "other-agent"}
    client.post("/v1/decisions", json=other)
    
    r = client.get("/v1/integrity/verify?service_name=test-agent")
    assert r.json()["integrity"]["total"] == 1


# ================================================================
# Compliance Tests
# ================================================================

def test_compliance_report_empty(client):
    r = client.get("/v1/compliance/report")
    assert r.status_code == 200
    data = r.json()
    assert data["report_type"] == "EU AI Act Compliance Assessment"
    assert data["summary"]["total"] == 0


def test_compliance_report_with_data(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    decision_id = r.json()["decision_id"]
    
    client.post(f"/v1/decisions/{decision_id}/incorrect", json={"reason": "wrong"})
    client.post(f"/v1/decisions/{decision_id}/correction", json={
        "correction": {"response": "Fixed."},
        "corrected_by": "agent_1"
    })
    
    r = client.get("/v1/compliance/report")
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["total"] == 1
    assert data["summary"]["corrected"] == 1
    assert data["ledger_integrity"]["valid"] is True
    assert data["eu_ai_act_mapping"]["article_12_record_keeping"]["status"] == "compliant"
    assert data["eu_ai_act_mapping"]["article_14_human_oversight"]["status"] == "compliant"


def test_compliance_html_report(client, sample_decision):
    client.post("/v1/decisions", json=sample_decision)
    r = client.get("/v1/compliance/report/html")
    assert r.status_code == 200
    assert "LoopGrid Compliance Report" in r.text


def test_export_decisions_json(client, sample_decision):
    client.post("/v1/decisions", json=sample_decision)
    r = client.get("/v1/export/decisions")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_export_decisions_csv(client, sample_decision):
    client.post("/v1/decisions", json=sample_decision)
    r = client.get("/v1/export/decisions?format=csv")
    assert r.status_code == 200
    assert "decision_id" in r.text
