from __future__ import annotations
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import LedgerEvent,CheckpointRecord
from .signing import signer
from .timestamping import request_rfc3161_timestamp


def create_checkpoint(db:Session,workspace_id:str,request_external_timestamp:bool=True)->dict:
    last=db.scalar(select(LedgerEvent).where(LedgerEvent.workspace_id==workspace_id).order_by(LedgerEvent.seq.desc()).limit(1))
    if not last:return {"workspace_id":workspace_id,"status":"empty","external_timestamp":False,"signer":signer.posture()}
    ts=request_rfc3161_timestamp(last.chain_hash) if request_external_timestamp else {"configured":False,"external_timestamp":False,"provider":"disabled"}
    cp=CheckpointRecord(checkpoint_id=f"cp_{uuid4().hex[:20]}",workspace_id=workspace_id,ledger_seq=last.seq,chain_hash=last.chain_hash,signature_b64=signer.sign_hash(last.chain_hash),key_id=signer.key_id,signature_algorithm=signer.algorithm,timestamp_provider=ts.get("provider","local_clock"),timestamp_status=ts.get("status") or ("imprint_verified" if ts.get("external_timestamp") else "not_configured"),timestamp_token_b64=ts.get("response_b64"),external_timestamp=bool(ts.get("external_timestamp")))
    db.add(cp);db.commit();db.refresh(cp)
    return checkpoint_to_dict(cp,ts)

def checkpoint_to_dict(cp:CheckpointRecord,ts_detail:dict|None=None)->dict:
    out={"checkpoint_id":cp.checkpoint_id,"workspace_id":cp.workspace_id,"ledger_seq":cp.ledger_seq,"chain_hash":cp.chain_hash,"created_at":cp.created_at.isoformat(),"signature":cp.signature_b64,"key_id":cp.key_id,"signature_algorithm":cp.signature_algorithm,"timestamp_provider":cp.timestamp_provider,"timestamp_status":cp.timestamp_status,"external_timestamp":cp.external_timestamp}
    if ts_detail:
        out["timestamp_detail"]={k:v for k,v in ts_detail.items() if k!="response_b64"}
    return out

def latest_checkpoint(db:Session,workspace_id:str)->CheckpointRecord|None:
    return db.scalar(select(CheckpointRecord).where(CheckpointRecord.workspace_id==workspace_id).order_by(CheckpointRecord.created_at.desc()).limit(1))


def latest_checkpoint_covering(db: Session, workspace_id: str, min_ledger_seq: int) -> CheckpointRecord | None:
    """Return the newest workspace checkpoint whose chain head covers min_ledger_seq."""
    return db.scalar(
        select(CheckpointRecord)
        .where(
            CheckpointRecord.workspace_id == workspace_id,
            CheckpointRecord.ledger_seq >= min_ledger_seq,
        )
        .order_by(CheckpointRecord.created_at.desc())
        .limit(1)
    )
