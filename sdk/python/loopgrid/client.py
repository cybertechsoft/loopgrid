from __future__ import annotations
from pathlib import Path
from typing import Any
import httpx


class LoopGrid:
    """Small synchronous client for the LoopGrid Evidence API.

    The SDK intentionally mirrors the Evidence Profile lifecycle rather than hiding it:
    create a consequential decision, append the model/policy/human/action/outcome evidence,
    then export or verify the resulting evidence record.
    """

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None,
                 workspace_id: str = "default", timeout: float = 30.0,
                 bearer_token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.timeout = timeout
        self.bearer_token = bearer_token

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.api_key:
            h["X-LoopGrid-Key"] = self.api_key
        if self.bearer_token:
            h["Authorization"] = "Bearer " + self.bearer_token.removeprefix("Bearer ").strip()
        return h

    def _request(self, method: str, path: str, **kwargs):
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        r = httpx.request(method, self.base_url + path, headers=headers, timeout=self.timeout, **kwargs)
        r.raise_for_status()
        if "json" in r.headers.get("content-type", ""):
            return r.json()
        return r.content

    # Decision capture -----------------------------------------------------
    def record_decision(self, **kwargs):
        kwargs.setdefault("workspace_id", self.workspace_id)
        return self._request("POST", "/api/v1/decisions", json=kwargs)

    def get_decision(self, decision_id: str):
        return self._request("GET", f"/api/v1/decisions/{decision_id}")

    def list_decisions(self, limit: int = 100):
        return self._request("GET", f"/api/v1/decisions?workspace_id={self.workspace_id}&limit={limit}")

    def add_event(self, decision_id: str, event_type: str, payload: dict[str, Any] | None = None,
                  actor_type: str = "system", actor_id: str = "loopgrid", **kwargs):
        return self._request("POST", f"/api/v1/decisions/{decision_id}/events", json={
            "event_type": event_type,
            "payload": payload or {},
            "actor_type": actor_type,
            "actor_id": actor_id,
            **kwargs,
        })

    def model_completed(self, decision_id: str, payload: dict[str, Any], actor_id: str = "agent", **kwargs):
        return self.add_event(decision_id, "model_completed", payload, "agent", actor_id, **kwargs)

    def policy_evaluated(self, decision_id: str, payload: dict[str, Any], actor_id: str = "policy", **kwargs):
        return self.add_event(decision_id, "policy_evaluated", payload, "policy", actor_id, **kwargs)

    def human_approved(self, decision_id: str, reviewer: str, reason: str = "", **kwargs):
        return self.add_event(decision_id, "human_approved", {
            "approved": True, "reviewer": reviewer, "reason": reason,
        }, "human", reviewer, **kwargs)

    def human_rejected(self, decision_id: str, reviewer: str, reason: str = "", **kwargs):
        return self.add_event(decision_id, "human_rejected", {
            "approved": False, "reviewer": reviewer, "reason": reason,
        }, "human", reviewer, **kwargs)

    def tool_executed(self, decision_id: str, payload: dict[str, Any], actor_id: str = "tool", **kwargs):
        return self.add_event(decision_id, "tool_executed", payload, "tool", actor_id, **kwargs)

    def outcome_observed(self, decision_id: str, payload: dict[str, Any], actor_id: str = "outcome-observer", **kwargs):
        return self.add_event(decision_id, "outcome_observed", payload, "system", actor_id, **kwargs)

    # Policy / review ------------------------------------------------------
    def policies(self):
        return self._request("GET", f"/api/v1/workspaces/{self.workspace_id}/policies")

    def evaluate_policy(self, policy_id: str, proposed_action: dict[str, Any],
                        authority: dict[str, Any] | None = None,
                        context: dict[str, Any] | None = None):
        return self._request("POST", f"/api/v1/workspaces/{self.workspace_id}/policies/evaluate", json={
            "policy_id": policy_id,
            "proposed_action": proposed_action,
            "authority": authority or {},
            "context": context or {},
        })

    def reviews(self):
        return self._request("GET", f"/api/v1/reviews?workspace_id={self.workspace_id}")

    def review(self, decision_id: str, action: str, reviewer: str, reason: str = ""):
        return self._request("POST", f"/api/v1/decisions/{decision_id}/review", json={
            "action": action, "reviewer": reviewer, "reason": reason,
        })

    # Evidence -------------------------------------------------------------
    def verify_workspace(self):
        return self._request("GET", f"/api/v1/integrity/verify?workspace_id={self.workspace_id}")

    def checkpoint(self):
        return self._request("POST", f"/api/v1/workspaces/{self.workspace_id}/checkpoint", json={})

    def export_evidence(self, decision_id: str, include_payloads: bool = True) -> bytes:
        return self._request(
            "GET",
            f"/api/v1/decisions/{decision_id}/evidence?include_payloads={str(bool(include_payloads)).lower()}",
        )

    def save_evidence(self, decision_id: str, path: str | Path, include_payloads: bool = True) -> Path:
        out = Path(path)
        out.write_bytes(self.export_evidence(decision_id, include_payloads=include_payloads))
        return out

    def payload_status(self, decision_id: str):
        return self._request("GET", f"/api/v1/decisions/{decision_id}/payload-status")

    def erase_payload(self, decision_id: str, reason: str = "customer_request"):
        return self._request("POST", f"/api/v1/decisions/{decision_id}/payload/erase", json={"reason": reason})

    def run_retention(self):
        return self._request("POST", f"/api/v1/workspaces/{self.workspace_id}/retention/run", json={})

    # Integrations / operations -------------------------------------------
    def replay(self, decision_id: str, **kwargs):
        return self._request("POST", f"/api/v1/decisions/{decision_id}/replay", json=kwargs)

    def system_info(self):
        return self._request("GET", "/api/v1/system/info")

    def readiness(self):
        return self._request("GET", "/ready")

    def pilot_readiness(self):
        return self._request("GET", "/api/v1/pilot/readiness")

    def ingest_otel(self, spans: list[dict[str, Any]]):
        return self._request("POST", "/api/v1/ingest/otel", json={"workspace_id": self.workspace_id, "spans": spans})

    def ingest_mcp(self, request: dict[str, Any], response: dict[str, Any] | None = None, **kwargs):
        return self._request("POST", "/api/v1/ingest/mcp", json={
            "workspace_id": self.workspace_id, "request": request, "response": response, **kwargs,
        })

    # Backward-compatible aliases ------------------------------------
    def decision(self, decision_id: str):
        return self.get_decision(decision_id)

    def decisions(self, limit: int = 100):
        return self.list_decisions(limit=limit)

    def verify(self):
        return self.verify_workspace()

    def evidence(self, decision_id: str, include_payloads: bool = True):
        return self.export_evidence(decision_id, include_payloads=include_payloads)
