from __future__ import annotations
import json
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import UsageEvent


def record_usage(db:Session, workspace_id:str, category:str, quantity:int=1, *, decision_id:str|None=None, metadata:dict|None=None)->None:
    db.add(UsageEvent(workspace_id=workspace_id,category=category,quantity=max(0,int(quantity)),decision_id=decision_id,metadata_json=json.dumps(metadata or {},ensure_ascii=False,separators=(",",":"))))
    db.commit()


def usage_summary(db:Session, workspace_id:str)->dict:
    rows=db.execute(select(UsageEvent.category,func.sum(UsageEvent.quantity)).where(UsageEvent.workspace_id==workspace_id).group_by(UsageEvent.category)).all()
    totals={str(cat):int(qty or 0) for cat,qty in rows}
    return {
        "workspace_id":workspace_id,
        "billing_unit":"consequential_decision",
        "billable_decisions":totals.get("decision",0),
        "totals":totals,
        "note":"One decision counts once even when it produces multiple signed evidence events.",
    }
