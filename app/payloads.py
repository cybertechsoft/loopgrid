from __future__ import annotations
import base64,json,os
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .crypto import canonical_json,sha256_hex
from .models import PayloadBlob,Workspace

def _load_key()->bytes:
    if settings.payload_master_key_b64:
        key=base64.b64decode(settings.payload_master_key_b64)
        if len(key)!=32:raise RuntimeError("LOOPGRID_PAYLOAD_MASTER_KEY_B64 must decode to 32 bytes")
        return key
    p=settings.payload_key_path;p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():
        key=p.read_bytes()
        if len(key)!=32:raise RuntimeError("Payload key file must contain exactly 32 bytes")
        return key
    key=os.urandom(32);p.write_bytes(key);return key

_MASTER_KEY=_load_key()

def commitment(payload:dict)->str:return sha256_hex(canonical_json(payload))

def store_full_payload(db:Session,*,workspace_id:str,event_id:str,payload:dict)->tuple[dict,str,str]:
    digest=commitment(payload);payload_id=f"pld_{uuid4().hex[:24]}";nonce=os.urandom(12)
    aad=canonical_json({"payload_id":payload_id,"event_id":event_id,"workspace_id":workspace_id,"sha256":digest})
    ciphertext=AESGCM(_MASTER_KEY).encrypt(nonce,canonical_json(payload),aad)
    ws=db.get(Workspace,workspace_id);days=(ws.retention_days if ws else 90);expires=datetime.now(timezone.utc)+timedelta(days=days)
    obj=PayloadBlob(payload_id=payload_id,event_id=event_id,workspace_id=workspace_id,ciphertext_b64=base64.b64encode(ciphertext).decode(),nonce_b64=base64.b64encode(nonce).decode(),payload_sha256=digest,expires_at=expires)
    db.add(obj)
    descriptor={"disclosure":"encrypted","payload_ref":payload_id,"payload_sha256":digest}
    return descriptor,digest,payload_id

def load_full_payload(db:Session,event_id:str)->dict|None:
    obj=db.scalar(select(PayloadBlob).where(PayloadBlob.event_id==event_id))
    if not obj or obj.erased_at or not obj.ciphertext_b64:return None
    aad=canonical_json({"payload_id":obj.payload_id,"event_id":obj.event_id,"workspace_id":obj.workspace_id,"sha256":obj.payload_sha256})
    try:
        raw=AESGCM(_MASTER_KEY).decrypt(base64.b64decode(obj.nonce_b64),base64.b64decode(obj.ciphertext_b64),aad)
        data=json.loads(raw);return data if commitment(data)==obj.payload_sha256 else None
    except Exception:return None

def erase_event_payload(db:Session,event_id:str,reason:str="requested")->bool:
    obj=db.scalar(select(PayloadBlob).where(PayloadBlob.event_id==event_id))
    if not obj or obj.erased_at:return False
    obj.ciphertext_b64="";obj.nonce_b64="";obj.erased_at=datetime.now(timezone.utc);obj.erasure_reason=reason;db.commit();return True

def erase_decision_payloads(db:Session,decision_event_ids:list[str],reason:str="requested")->int:
    count=0
    for event_id in decision_event_ids:count+=1 if erase_event_payload(db,event_id,reason) else 0
    return count

def erase_expired_payloads(db:Session,workspace_id:str,now:datetime|None=None)->int:
    now=now or datetime.now(timezone.utc);rows=list(db.scalars(select(PayloadBlob).where(PayloadBlob.workspace_id==workspace_id,PayloadBlob.erased_at.is_(None),PayloadBlob.expires_at<=now)))
    count=0
    for row in rows:
        row.ciphertext_b64="";row.nonce_b64="";row.erased_at=now;row.erasure_reason="retention_expired";count+=1
    db.commit();return count

def payload_status(db:Session,event_id:str)->dict:
    obj=db.scalar(select(PayloadBlob).where(PayloadBlob.event_id==event_id))
    if not obj:return {"mode":"not_vaulted","available":False}
    return {"mode":"encrypted_vault","payload_id":obj.payload_id,"available":not bool(obj.erased_at),"sha256":obj.payload_sha256,"expires_at":obj.expires_at.isoformat() if obj.expires_at else None,"erased_at":obj.erased_at.isoformat() if obj.erased_at else None,"erasure_reason":obj.erasure_reason}
