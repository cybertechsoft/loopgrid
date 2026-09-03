from __future__ import annotations
import json
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import LedgerEvent, Workspace
from .crypto import canonical_json, sha256_hex
from .privacy import apply_privacy
from .payloads import store_full_payload, load_full_payload, payload_status
from .signing import signer

GENESIS = "0" * 64
KEY_ID = signer.key_id
SIGNATURE_ALGORITHM = signer.algorithm
# Compatibility exports for existing application code.
public_key = getattr(signer,"public",None)
private_key = getattr(signer,"private",None)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


def _lock_workspace_for_append(db:Session,workspace_id:str)->None:
    """Serialize chain-head updates per workspace on transactional databases.

    A hash chain must have one authoritative predecessor. PostgreSQL row locking prevents
    two concurrent appenders from reading the same chain head and creating a fork. SQLite
    remains the zero-setup developer backend and serializes writes at the database level.
    """
    bind=db.get_bind();dialect=getattr(getattr(bind,"dialect",None),"name","")
    if dialect and dialect!="sqlite":
        ws=db.scalar(select(Workspace).where(Workspace.workspace_id==workspace_id).with_for_update())
        if ws is None:
            raise KeyError(f"Workspace not found: {workspace_id}")


def _privacy_projection(db:Session,*,event_id:str,workspace_id:str,payload:dict,privacy_mode:str)->tuple[dict,str|None]:
    ws=db.get(Workspace,workspace_id);custom=[]
    if ws and getattr(ws,"redaction_fields_json",None):
        try:custom=json.loads(ws.redaction_fields_json)
        except Exception:custom=[]
    if privacy_mode=="full":
        descriptor,digest,_=store_full_payload(db,workspace_id=workspace_id,event_id=event_id,payload=payload)
        return descriptor,digest
    return apply_privacy(payload,privacy_mode,custom)


def append_event(
    db: Session, *, decision_id: str, event_type: str, payload: dict,
    actor_type: str = "system", actor_id: str = "loopgrid", workspace_id: str = "default",
    privacy_mode: str = "full", idempotency_key: str | None = None,
) -> LedgerEvent:
    # Chain-head selection and append are one per-workspace critical section on PostgreSQL.
    _lock_workspace_for_append(db,workspace_id)
    if idempotency_key:
        existing = db.scalar(select(LedgerEvent).where(
            LedgerEvent.workspace_id == workspace_id,
            LedgerEvent.idempotency_key == idempotency_key,
        ))
        if existing:
            return existing

    last = db.scalar(select(LedgerEvent).where(LedgerEvent.workspace_id == workspace_id).order_by(LedgerEvent.seq.desc()).limit(1))
    previous_chain_hash = last.chain_hash if last else GENESIS
    event_id = _new_id("evt")
    occurred_at = datetime.now(timezone.utc)
    stored_payload, payload_commitment = _privacy_projection(db,event_id=event_id,workspace_id=workspace_id,payload=payload,privacy_mode=privacy_mode)

    signed_body = {
        "event_id": event_id, "decision_id": decision_id, "workspace_id": workspace_id,
        "event_type": event_type, "occurred_at": occurred_at.isoformat(),
        "actor": {"type": actor_type, "id": actor_id}, "privacy_mode": privacy_mode,
        "payload_commitment": payload_commitment, "payload": stored_payload,
    }
    content_hash = sha256_hex(canonical_json(signed_body))
    chain_hash = sha256_hex(bytes.fromhex(previous_chain_hash) + bytes.fromhex(content_hash))
    signature = signer.sign_hash(chain_hash)

    ev = LedgerEvent(
        event_id=event_id, decision_id=decision_id, workspace_id=workspace_id, event_type=event_type,
        occurred_at=occurred_at, actor_type=actor_type, actor_id=actor_id,
        payload_json=json.dumps(stored_payload, ensure_ascii=False, separators=(",", ":")),
        privacy_mode=privacy_mode, payload_commitment=payload_commitment,
        content_hash=content_hash, previous_chain_hash=previous_chain_hash, chain_hash=chain_hash,
        signature_b64=signature, key_id=signer.key_id, signature_algorithm=signer.algorithm,idempotency_key=idempotency_key,
    )
    db.add(ev); db.commit(); db.refresh(ev)
    return ev


def _rebuild_signed_body(ev: LedgerEvent) -> dict:
    occurred = ev.occurred_at
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=timezone.utc)
    return {
        "event_id": ev.event_id, "decision_id": ev.decision_id, "workspace_id": ev.workspace_id,
        "event_type": ev.event_type, "occurred_at": occurred.isoformat(),
        "actor": {"type": ev.actor_type, "id": ev.actor_id}, "privacy_mode": ev.privacy_mode,
        "payload_commitment": ev.payload_commitment, "payload": json.loads(ev.payload_json),
    }


def event_to_dict(ev: LedgerEvent,db:Session|None=None,*,disclose_payload:bool=True) -> dict:
    signed_body=_rebuild_signed_body(ev);signed_payload=signed_body["payload"];payload=signed_payload;available=None
    if ev.privacy_mode=="full":
        available=False
        if db is not None and disclose_payload:
            raw=load_full_payload(db,ev.event_id)
            if raw is not None:payload=raw;available=True
    out={
        **signed_body,"payload":payload,
        "proof": {
            "content_hash": ev.content_hash, "previous_chain_hash": ev.previous_chain_hash,
            "chain_hash": ev.chain_hash, "signature": ev.signature_b64, "key_id": ev.key_id,
            "signature_algorithm":ev.signature_algorithm,
        },
        "seq": ev.seq,
    }
    if payload is not signed_payload:out["signed_payload"]=signed_payload
    if ev.privacy_mode=="full":out["payload_available"]=available;out["payload_status"]=payload_status(db,ev.event_id) if db is not None else None
    return out


def verify_ledger(db: Session, decision_id: str | None = None, workspace_id: str | None = None) -> dict:
    if decision_id and not workspace_id:
        first = db.scalar(select(LedgerEvent).where(LedgerEvent.decision_id == decision_id).order_by(LedgerEvent.seq.asc()).limit(1))
        workspace_id = first.workspace_id if first else None
    query = select(LedgerEvent)
    if workspace_id:
        query = query.where(LedgerEvent.workspace_id == workspace_id)
    events = list(db.scalars(query.order_by(LedgerEvent.seq.asc())))
    expected_prev = GENESIS
    failures: list[dict] = []
    checked = 0
    for ev in events:
        body = _rebuild_signed_body(ev)
        expected_content = sha256_hex(canonical_json(body))
        expected_chain = sha256_hex(bytes.fromhex(expected_prev) + bytes.fromhex(expected_content))
        reasons = []
        if ev.content_hash != expected_content: reasons.append("content_hash_mismatch")
        if ev.previous_chain_hash != expected_prev: reasons.append("previous_chain_hash_mismatch")
        if ev.chain_hash != expected_chain: reasons.append("chain_hash_mismatch")
        # Current server validates with the active signer only. Offline bundles carry the public key
        # required to verify historical signatures independently.
        if ev.key_id==signer.key_id and not signer.verify_hash(ev.chain_hash, ev.signature_b64): reasons.append("signature_invalid")
        elif ev.key_id!=signer.key_id: reasons.append("signing_key_not_loaded")
        if reasons:
            failures.append({"seq": ev.seq, "event_id": ev.event_id, "decision_id": ev.decision_id, "reasons": reasons})
        expected_prev = ev.chain_hash
        if decision_id is None or ev.decision_id == decision_id: checked += 1
    return {
        "valid": len(failures) == 0, "checked_events": checked, "total_ledger_events": len(events),
        "failures": failures, "key_id": signer.key_id, "signature_algorithm":signer.algorithm,"signer_provider":signer.provider,"workspace_id": workspace_id,
        "algorithm": f"{signer.algorithm} + SHA-256 workspace hash chain", "chain_scope": "workspace",
    }
