from __future__ import annotations
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import AuditLog

def record_audit(db:Session,workspace_id:str,action:str,*,actor:str="system",target_type:str="workspace",target_id:str="",detail:dict|None=None):
    row=AuditLog(workspace_id=workspace_id,actor=actor,action=action,target_type=target_type,target_id=target_id,detail_json=json.dumps(detail or {},ensure_ascii=False,separators=(",",":"))); db.add(row); db.commit(); db.refresh(row); return row

def list_audit(db:Session,workspace_id:str,limit:int=100):
    rows=list(db.scalars(select(AuditLog).where(AuditLog.workspace_id==workspace_id).order_by(AuditLog.audit_id.desc()).limit(limit)))
    return [{"audit_id":r.audit_id,"workspace_id":r.workspace_id,"actor":r.actor,"action":r.action,"target_type":r.target_type,"target_id":r.target_id,"detail":json.loads(r.detail_json),"created_at":r.created_at.isoformat()} for r in rows]
