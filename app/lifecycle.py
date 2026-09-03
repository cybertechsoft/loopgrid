from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LifecycleError(ValueError):
    code: str
    message: str
    def __str__(self): return self.message


def _types(events:list[dict])->list[str]:
    return [str(e.get("event_type")) for e in events]


def _last(events:list[dict], event_types:set[str]):
    return next((e for e in reversed(events) if e.get("event_type") in event_types), None)


def lifecycle_state(events:list[dict])->dict:
    """Derive the operational lifecycle without mutating evidence.

    The ledger remains the source of truth. This state is a deterministic projection used
    by the API/UI to explain what is expected next.
    """
    if not events:
        return {"state":"missing","label":"Decision not found","terminal":False,"expected_next":["decision_created"]}
    types=_types(events)
    policy=_last(events,{"policy_evaluated"})
    review=_last(events,{"human_approved","human_rejected","human_adjudicated"})
    execution=_last(events,{"tool_executed","tool_result","mcp_tool_result"})
    outcome=_last(events,{"outcome_observed"})
    p=(policy or {}).get("payload") or {}
    p_decision=p.get("decision")
    review_type=(review or {}).get("event_type")

    if outcome:
        return {"state":"evidence_complete","label":"Evidence complete","terminal":True,"expected_next":["replay_executed","incident_flagged","human_adjudicated"]}
    if p_decision in {"blocked","block"}:
        return {"state":"blocked","label":"Blocked by policy","terminal":True,"expected_next":["outcome_observed","replay_executed","human_adjudicated"]}
    if review_type=="human_rejected":
        return {"state":"rejected","label":"Rejected by human reviewer","terminal":True,"expected_next":["outcome_observed","replay_executed","human_adjudicated"]}
    if execution:
        return {"state":"awaiting_outcome","label":"In progress · awaiting observed outcome","terminal":False,"expected_next":["outcome_observed"]}
    if review_type in {"human_approved","human_adjudicated"}:
        return {"state":"approved_awaiting_execution","label":"In progress · approved, awaiting execution","terminal":False,"expected_next":["tool_requested","tool_executed","mcp_tool_requested","mcp_tool_result","outcome_observed"]}
    if p_decision=="human_approval_required":
        return {"state":"awaiting_human_review","label":"In progress · awaiting human review","terminal":False,"expected_next":["human_approved","human_rejected"]}
    if p_decision=="auto_allowed":
        return {"state":"authorized_awaiting_execution","label":"In progress · authorized, awaiting execution","terminal":False,"expected_next":["tool_requested","tool_executed","mcp_tool_requested","mcp_tool_result","outcome_observed"]}
    if policy:
        return {"state":"policy_evaluated","label":"Policy evaluated","terminal":False,"expected_next":["human_approved","human_rejected","tool_requested","tool_executed","outcome_observed"]}
    if "model_completed" in types:
        return {"state":"model_captured","label":"Model evidence captured","terminal":False,"expected_next":["policy_evaluated","tool_requested","tool_executed","outcome_observed"]}
    return {"state":"captured","label":"Decision captured","terminal":False,"expected_next":["model_completed","policy_evaluated","tool_requested","tool_executed","outcome_observed"]}


def validate_append(events:list[dict], event_type:str)->None:
    """Reject impossible consequential transitions while keeping append-only extensions open."""
    if not events:
        raise LifecycleError("decision_missing","Cannot append evidence before decision_created")
    types=_types(events)
    policy=_last(events,{"policy_evaluated"})
    p=(policy or {}).get("payload") or {}
    p_decision=p.get("decision")
    review=_last(events,{"human_approved","human_rejected","human_adjudicated"})
    review_type=(review or {}).get("event_type")

    if event_type=="policy_evaluated" and "policy_evaluated" in types:
        raise LifecycleError("policy_already_evaluated","Production policy evidence is already recorded; use replay for counterfactual evaluation")

    if event_type in {"human_approved","human_rejected"}:
        if not policy:
            raise LifecycleError("review_without_policy","Human review requires a recorded policy_evaluated event")
        if p_decision!="human_approval_required":
            raise LifecycleError("review_not_required",f"Policy result is {p_decision or 'unknown'}; human approval/rejection is not the expected transition")
        if review_type in {"human_approved","human_rejected"}:
            raise LifecycleError("review_already_recorded","A human review decision is already recorded; use human_adjudicated for later adjudication")

    if event_type in {"tool_requested","tool_executed","tool_result","mcp_tool_requested","mcp_tool_result"}:
        if p_decision in {"blocked","block"}:
            raise LifecycleError("action_blocked","Policy blocked the action; execution evidence cannot be appended")
        if p_decision=="human_approval_required" and review_type!="human_approved":
            raise LifecycleError("approval_required","The action requires a signed human approval before execution")
        if review_type=="human_rejected":
            raise LifecycleError("action_rejected","The action was rejected by a human reviewer")

    if event_type=="outcome_observed" and policy:
        if p_decision=="human_approval_required" and not review:
            raise LifecycleError("approval_required","Cannot record an executed outcome before the required human review")
        # blocked/rejected decisions may record a non-execution outcome for closure.
        if p_decision not in {"blocked","block"} and review_type!="human_rejected":
            if not any(t in types for t in {"tool_executed","tool_result","mcp_tool_result"}):
                raise LifecycleError("execution_missing","Observed outcome requires prior execution/tool-result evidence")
