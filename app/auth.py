from __future__ import annotations
import hashlib,json,secrets
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import ApiKey,Workspace


def _hash(raw): return hashlib.sha256(raw.encode()).hexdigest()

def _aware(dt):
    if dt is None:return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def ensure_workspace(db,workspace_id="default",name="Acme Support",privacy_mode="full"):
    ws=db.get(Workspace,workspace_id)
    if ws:return ws
    ws=Workspace(workspace_id=workspace_id,name=name,privacy_mode=privacy_mode,retention_days=90,redaction_fields_json="[]");db.add(ws);db.commit();db.refresh(ws);return ws

def create_workspace(db,name,environment,privacy_mode,retention_days=90,redaction_fields=None):
    ws=Workspace(workspace_id=f"ws_{uuid4().hex[:16]}",name=name,environment=environment,privacy_mode=privacy_mode,retention_days=retention_days,redaction_fields_json=json.dumps(redaction_fields or []));db.add(ws);db.commit();db.refresh(ws);return ws

def create_api_key(db,workspace_id,name,scopes=None,*,description="",expires_in_days:int|None=None,created_by="system",rotated_from_key_id:str|None=None):
    ensure_workspace(db,workspace_id)
    raw="lg_live_"+secrets.token_urlsafe(28)
    scope_list=sorted(set(scopes or ["ingest","read"]))
    expires_at=datetime.now(timezone.utc)+timedelta(days=expires_in_days) if expires_in_days else None
    obj=ApiKey(key_id=f"key_{uuid4().hex[:16]}",workspace_id=workspace_id,name=name,description=description or "",key_prefix=raw[:14],key_hash=_hash(raw),scopes=",".join(scope_list),created_by=created_by or "system",expires_at=expires_at,rotated_from_key_id=rotated_from_key_id)
    db.add(obj);db.commit();db.refresh(obj);return obj,raw

def key_scopes(obj): return set((obj.scopes or "").split(",")) if obj else set()

def key_status(obj)->str:
    if not obj:return "missing"
    if obj.revoked_at:return "revoked"
    if obj.expires_at and _aware(obj.expires_at)<=datetime.now(timezone.utc):return "expired"
    return "active"

def authenticate_key(db,raw,required_scope=None):
    if not raw:return None
    obj=db.scalar(select(ApiKey).where(ApiKey.key_hash==_hash(raw)))
    if not obj or key_status(obj)!="active":return None
    if required_scope and required_scope not in key_scopes(obj) and "admin" not in key_scopes(obj):return None
    obj.last_used_at=datetime.now(timezone.utc);db.commit()
    return obj

def revoke_key(db,key_id):
    obj=db.get(ApiKey,key_id)
    if not obj:return False
    if not obj.revoked_at:obj.revoked_at=datetime.now(timezone.utc);db.commit()
    return True

def rotate_key(db,key_id,*,created_by="system",expires_in_days:int|None=None):
    """Rotate a key atomically: create replacement and revoke predecessor in one commit."""
    old=db.get(ApiKey,key_id)
    if not old:
        return None,None,None
    if key_status(old)!="active":
        return old,None,None

    raw="lg_live_"+secrets.token_urlsafe(28)
    expires_at=datetime.now(timezone.utc)+timedelta(days=expires_in_days) if expires_in_days else None
    obj=ApiKey(
        key_id=f"key_{uuid4().hex[:16]}",workspace_id=old.workspace_id,name=old.name,
        description=old.description or "",key_prefix=raw[:14],key_hash=_hash(raw),
        scopes=old.scopes,created_by=created_by or "system",expires_at=expires_at,
        rotated_from_key_id=old.key_id,
    )
    old.revoked_at=datetime.now(timezone.utc)
    db.add(obj)
    try:
        db.commit();db.refresh(obj);db.refresh(old)
    except Exception:
        db.rollback();raise
    return old,obj,raw
