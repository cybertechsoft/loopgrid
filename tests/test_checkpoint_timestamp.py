from __future__ import annotations

import json
import zipfile
from io import BytesIO

from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def reset():
    r = client.delete("/api/v1/demo/reset")
    assert r.status_code == 200


def _manifest(bundle: bytes) -> dict:
    with zipfile.ZipFile(BytesIO(bundle)) as z:
        return json.loads(z.read("manifest.json"))


def test_stale_checkpoint_is_not_attached_to_later_decision_evidence():
    reset()
    first = client.post("/api/v1/demo/refund").json()["summary"]["decision_id"]
    cp = client.post("/api/v1/workspaces/default/checkpoint", json={}).json()
    assert cp["checkpoint_id"]
    later = client.post(
        "/api/v1/decisions",
        json={"workspace_id": "default", "decision_type": "later", "agent": {"id": "a"}},
    ).json()["decision_id"]
    manifest = _manifest(client.get(f"/api/v1/decisions/{later}/evidence").content)
    assert manifest["checkpoint"] is None


def test_covering_checkpoint_is_linked_with_proof_only_witnesses():
    reset()
    target = client.post(
        "/api/v1/decisions",
        json={"workspace_id": "default", "decision_type": "target", "agent": {"id": "a"}},
    ).json()["decision_id"]
    # Intervening unrelated workspace event after target decision.
    client.post(
        "/api/v1/decisions",
        json={"workspace_id": "default", "decision_type": "other", "agent": {"id": "b"}},
    )
    cp = client.post("/api/v1/workspaces/default/checkpoint", json={}).json()
    bundle = client.get(f"/api/v1/decisions/{target}/evidence").content
    with zipfile.ZipFile(BytesIO(bundle)) as z:
        manifest = json.loads(z.read("manifest.json"))
        witnesses = [json.loads(x) for x in z.read("chain-witness.jsonl").decode().splitlines() if x.strip()]
    assert manifest["checkpoint"]["checkpoint_id"] == cp["checkpoint_id"]
    assert witnesses
    assert max(w["seq"] for w in witnesses) == cp["ledger_seq"]
