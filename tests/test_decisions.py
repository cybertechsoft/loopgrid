"""Tests for decision recording, retrieval, and hash chain."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_record_decision(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    assert r.status_code == 200
    data = r.json()
    assert data["decision_id"].startswith("dec_")
    assert data["service_name"] == "test-agent"
    assert data["status"] == "recorded"
    assert data["content_hash"] is not None
    assert data["chain_hash"] is not None
    assert len(data["content_hash"]) == 64  # SHA-256 hex


def test_get_decision(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    decision_id = r.json()["decision_id"]
    
    r = client.get(f"/v1/decisions/{decision_id}")
    assert r.status_code == 200
    assert r.json()["decision_id"] == decision_id


def test_get_decision_not_found(client):
    r = client.get("/v1/decisions/dec_doesnotexist")
    assert r.status_code == 404


def test_list_decisions(client, sample_decision):
    client.post("/v1/decisions", json=sample_decision)
    client.post("/v1/decisions", json=sample_decision)
    
    r = client.get("/v1/decisions")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["decisions"]) == 2


def test_list_filter_by_service(client, sample_decision):
    client.post("/v1/decisions", json=sample_decision)
    other = {**sample_decision, "service_name": "other-agent"}
    client.post("/v1/decisions", json=other)
    
    r = client.get("/v1/decisions?service_name=test-agent")
    assert r.json()["total"] == 1


def test_mark_incorrect(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    decision_id = r.json()["decision_id"]
    
    r = client.post(f"/v1/decisions/{decision_id}/incorrect", json={"reason": "Missed billing issue"})
    assert r.status_code == 200
    assert r.json()["status"] == "incorrect"
    assert r.json()["incorrect_reason"] == "Missed billing issue"


def test_attach_correction(client, sample_decision):
    r = client.post("/v1/decisions", json=sample_decision)
    decision_id = r.json()["decision_id"]
    
    r = client.post(f"/v1/decisions/{decision_id}/correction", json={
        "correction": {"response": "Refund initiated."},
        "corrected_by": "agent_42",
        "notes": "Duplicate charge"
    })
    assert r.status_code == 200
    assert r.json()["status"] == "corrected"
    assert r.json()["correction"]["corrected_by"] == "agent_42"


def test_hash_chain_links(client, sample_decision):
    """Each decision's chain_hash should be different (linked to previous)."""
    r1 = client.post("/v1/decisions", json=sample_decision)
    r2 = client.post("/v1/decisions", json=sample_decision)
    
    # Same content but different chain hashes (chained to different predecessors)
    assert r1.json()["content_hash"] == r2.json()["content_hash"]
    assert r1.json()["chain_hash"] != r2.json()["chain_hash"]
