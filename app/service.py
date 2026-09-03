from __future__ import annotations
from collections import Counter
from uuid import uuid4
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import LedgerEvent, Workspace
from .ledger import append_event, event_to_dict, verify_ledger
from .auth import ensure_workspace
from .version import EVIDENCE_PROFILE
from .config import settings
from .lifecycle import lifecycle_state, validate_append
from .usage import record_usage


def _workspace_privacy(db: Session, workspace_id: str, requested: str | None = None) -> str:
    ws = ensure_workspace(db, workspace_id)
    return requested or ws.privacy_mode


def create_decision(db: Session, data: dict) -> dict:
    workspace_id = data.get("workspace_id") or "default"
    privacy_mode = _workspace_privacy(db, workspace_id, data.get("privacy_mode"))
    idem = data.get("idempotency_key")
    if idem:
        existing = db.scalar(select(LedgerEvent).where(LedgerEvent.workspace_id == workspace_id, LedgerEvent.idempotency_key == idem))
        if existing:
            return {"decision_id": existing.decision_id, "event": event_to_dict(existing,db), "idempotent_replay": True}
    decision_id = f"dec_{uuid4().hex[:24]}"
    payload = {
        "spec_version": f"loopgrid/{EVIDENCE_PROFILE}", "decision_type": data["decision_type"],
        "service_name": data.get("service_name", "ai-agent"), "agent": data.get("agent", {}),
        "authority": data.get("authority", {}), "model": data.get("model", {}),
        "context": data.get("context", {}), "input": data.get("input", {}),
        "proposed_action": data.get("proposed_action", {}), "metadata": data.get("metadata", {}),
    }
    ev = append_event(db, decision_id=decision_id, event_type="decision_created", payload=payload,
        actor_type="agent", actor_id=payload.get("agent", {}).get("id", "unknown-agent"),
        workspace_id=workspace_id, privacy_mode=privacy_mode, idempotency_key=idem)
    record_usage(db, workspace_id, "decision", 1, decision_id=decision_id, metadata={"decision_type": data["decision_type"]})
    return {"decision_id": decision_id, "event": event_to_dict(ev,db)}


def add_event(db: Session, decision_id: str, event_type: str, payload: dict, actor_type: str, actor_id: str,
              privacy_mode: str | None = None, idempotency_key: str | None = None) -> dict:
    first = db.scalar(select(LedgerEvent).where(LedgerEvent.decision_id == decision_id).order_by(LedgerEvent.seq.asc()).limit(1))
    if not first:
        raise KeyError(decision_id)

    # Idempotent retries must be resolved *before* lifecycle validation. Otherwise a retry of
    # an already-recorded approval/execution could be rejected because the lifecycle has moved
    # on since the first request. Idempotency keys are workspace-scoped; reusing one for a
    # different decision is an explicit conflict rather than silently returning unrelated proof.
    if idempotency_key:
        existing = db.scalar(select(LedgerEvent).where(
            LedgerEvent.workspace_id == first.workspace_id,
            LedgerEvent.idempotency_key == idempotency_key,
        ))
        if existing:
            if existing.decision_id != decision_id:
                from .lifecycle import LifecycleError
                raise LifecycleError("idempotency_conflict", "Idempotency key is already bound to another decision in this workspace")
            return event_to_dict(existing, db)

    if settings.enforce_lifecycle:
        validate_append(get_events(db, decision_id), event_type)
    mode = privacy_mode or first.privacy_mode
    ev = append_event(db, decision_id=decision_id, event_type=event_type, payload=payload,
        actor_type=actor_type, actor_id=actor_id, workspace_id=first.workspace_id,
        privacy_mode=mode, idempotency_key=idempotency_key)
    return event_to_dict(ev,db)


def get_events(db: Session, decision_id: str) -> list[dict]:
    rows = list(db.scalars(select(LedgerEvent).where(LedgerEvent.decision_id == decision_id).order_by(LedgerEvent.seq.asc())))
    if not rows: raise KeyError(decision_id)
    return [event_to_dict(r,db) for r in rows]


def summarize_decision(events: list[dict]) -> dict:
    created = next(e for e in events if e["event_type"] == "decision_created")
    p = created["payload"]
    latest_policy = next((e for e in reversed(events) if e["event_type"] == "policy_evaluated"), None)
    approval = next((e for e in reversed(events) if e["event_type"] in {"human_approved", "human_rejected", "human_adjudicated"}), None)
    outcome = next((e for e in reversed(events) if e["event_type"] == "outcome_observed"), None)
    tool = next((e for e in reversed(events) if e["event_type"] in {"tool_executed", "tool_requested", "mcp_tool_requested"}), None)
    replay = next((e for e in reversed(events) if e["event_type"] == "replay_executed"), None)
    proof_only = created.get("privacy_mode") == "proof_only"
    return {
        "decision_id": created["decision_id"], "workspace_id": created["workspace_id"],
        "privacy_mode": created.get("privacy_mode", "full"), "decision_type": p.get("decision_type") if not proof_only else "protected_decision",
        "service_name": p.get("service_name") if isinstance(p, dict) else None, "created_at": created["occurred_at"],
        "agent": p.get("agent", {}) if isinstance(p, dict) else {}, "authority": p.get("authority", {}) if isinstance(p, dict) else {},
        "model": p.get("model", {}) if isinstance(p, dict) else {}, "context": p.get("context", {}) if isinstance(p, dict) else {},
        "input": p.get("input", {}) if isinstance(p, dict) else {}, "proposed_action": p.get("proposed_action", {}) if isinstance(p, dict) else {},
        "metadata": p.get("metadata", {}) if isinstance(p, dict) else {}, "policy": latest_policy["payload"] if latest_policy else None,
        "approval": approval["payload"] if approval else None, "approval_event": approval["event_type"] if approval else None,
        "tool": tool["payload"] if tool else None, "outcome": outcome["payload"] if outcome else None,
        "last_replay": replay["payload"] if replay else None, "event_count": len(events),
        "lifecycle": lifecycle_state(events),
    }


def evidence_coverage(summary: dict, verification: dict | None = None) -> dict:
    """Return lifecycle-aware evidence coverage.

    A pending control is not the same thing as missing evidence. For example, a policy-gated
    action awaiting human review is intentionally incomplete, not defective. `score` remains a
    useful progress percentage while `state`/`complete` explain the lifecycle.
    """
    policy = summary.get("policy") or {}
    decision = policy.get("decision")
    approval = summary.get("approval") or None
    approval_event = summary.get("approval_event")
    proof_only = summary.get("privacy_mode") == "proof_only"
    rejected = approval_event == "human_rejected"
    blocked = decision in {"blocked", "block"}
    approval_required = decision == "human_approval_required"

    def status(present: bool, *, pending: bool = False, na: bool = False):
        if na: return "not_applicable"
        if present: return "present"
        if pending: return "pending"
        return "missing"

    rows = [
        ("agent_identity", "Agent identity", status(bool((summary.get("agent") or {}).get("id")) or proof_only)),
        ("authority", "Delegated authority", status(bool(summary.get("authority")) or proof_only)),
        ("model", "Model provenance", status(bool((summary.get("model") or {}).get("name")) or proof_only)),
        ("context", "Prompt / context version", status(bool(summary.get("context")) or proof_only)),
        ("policy", "Policy provenance", status(bool(policy.get("version") or policy.get("policy_id")) or proof_only)),
        ("human_oversight", "Human oversight", status(bool(approval), pending=approval_required and not approval, na=not approval_required)),
        ("action", "Action evidence", status(bool(summary.get("tool")) or proof_only, pending=(approval_required and not approval) or (approval_event=="human_approved" and not summary.get("tool")), na=blocked or rejected)),
        ("outcome", "Observed outcome", status(bool(summary.get("outcome")) or proof_only, pending=(approval_required and not approval) or (approval_event=="human_approved" and not summary.get("outcome")), na=rejected)),
        ("cryptographic_proof", "Cryptographic proof", status(bool((verification or {}).get("valid")))),
    ]
    applicable=[r for r in rows if r[2] != "not_applicable"]
    passed=sum(st=="present" for _,_,st in applicable)
    pending=sum(st=="pending" for _,_,st in applicable)
    missing=sum(st=="missing" for _,_,st in applicable)
    score=round(passed/max(1,len(applicable))*100)

    if verification is not None and not verification.get("valid"):
        state="integrity_alert"; label="Integrity alert"
    elif approval_required and not approval:
        state="awaiting_human_review"; label="In progress · awaiting human review"
    elif approval_event=="human_approved" and not summary.get("outcome"):
        state="awaiting_execution_outcome"; label="In progress · awaiting execution/outcome"
    elif missing:
        state="incomplete"; label="Incomplete evidence"
    else:
        state="complete"; label="Evidence complete"

    return {
        "score": score, "passed": passed, "total": len(applicable), "pending": pending, "missing": missing,
        "complete": state == "complete", "state": state, "label": label,
        "checks": [{"id": i, "label": l, "present": st == "present", "status": st} for i,l,st in rows]
    }


def list_decisions(db: Session, limit: int = 100, workspace_id: str | None = None) -> list[dict]:
    q = select(LedgerEvent.decision_id).where(LedgerEvent.event_type == "decision_created")
    if workspace_id: q = q.where(LedgerEvent.workspace_id == workspace_id)
    ids = list(db.scalars(q.order_by(LedgerEvent.seq.desc()).limit(limit)))
    out=[]
    for did in ids:
        try:
            s=summarize_decision(get_events(db,did)); s["coverage"] = evidence_coverage(s,{"valid":True}); out.append(s)
        except KeyError: pass
    return out


def dashboard(db: Session, workspace_id: str = "default") -> dict:
    ensure_workspace(db, workspace_id)
    decisions=list_decisions(db,500,workspace_id)
    event_count=db.scalar(select(func.count()).select_from(LedgerEvent).where(LedgerEvent.workspace_id==workspace_id)) or 0
    verified=verify_ledger(db,workspace_id=workspace_id)
    outcomes=Counter((d.get("outcome") or {}).get("status","pending") for d in decisions)
    approvals=sum(d.get("approval_event")=="human_approved" for d in decisions)
    rejections=sum(d.get("approval_event")=="human_rejected" for d in decisions)
    completed_reviews=approvals+rejections
    pending_reviews=sum((d.get("policy") or {}).get("decision")=="human_approval_required" and not d.get("approval") for d in decisions)
    blocks=sum((d.get("policy") or {}).get("decision") in {"block","blocked"} for d in decisions)
    completed=sum(bool(d.get("outcome")) for d in decisions)
    auto_allowed=sum((d.get("policy") or {}).get("decision")=="auto_allowed" for d in decisions)
    scores=[(d.get("coverage") or {}).get("score",0) for d in decisions]
    ws=db.get(Workspace,workspace_id)
    return {"workspace_id":workspace_id,"workspace_name":ws.name,"privacy_mode":ws.privacy_mode,
        "decisions":len(decisions),"events":event_count,"integrity_valid":verified["valid"],"human_approvals":approvals,"human_rejections":rejections,"completed_reviews":completed_reviews,"pending_reviews":pending_reviews,
        "policy_blocks":blocks,"outcomes":dict(outcomes),"outcome_verified":completed,"auto_allowed":auto_allowed,
        "average_evidence_coverage":round(sum(scores)/len(scores)) if scores else 0,"key_id":verified.get("key_id")}
