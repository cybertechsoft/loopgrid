from __future__ import annotations
import json
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .models import PolicyVersion
from .crypto import canonical_json,sha256_hex


def _policy_digest_fields(workspace_id,policy_id,version,rule):
    return {"workspace_id":workspace_id,"policy_id":policy_id,"version":version,"rule":rule}

def policy_digest(workspace_id,policy_id,version,rule):
    return sha256_hex(canonical_json(_policy_digest_fields(workspace_id,policy_id,version,rule)))

def policy_to_dict(p):
    rule=json.loads(p.rule_json)
    return {"workspace_id":p.workspace_id,"policy_id":p.policy_id,"name":p.name,"version":p.version,"rule":rule,"policy_digest":policy_digest(p.workspace_id,p.policy_id,p.version,rule),"active":p.active,"created_at":p.created_at.isoformat()}

def create_policy(db,workspace_id,*,policy_id,name,version,rule,active=True):
    if active: db.execute(update(PolicyVersion).where(PolicyVersion.workspace_id==workspace_id,PolicyVersion.policy_id==policy_id).values(active=False))
    p=PolicyVersion(workspace_id=workspace_id,policy_id=policy_id,name=name,version=version,rule_json=json.dumps(rule,ensure_ascii=False,separators=(",",":")),active=active); db.add(p); db.commit(); db.refresh(p); return policy_to_dict(p)

def ensure_refund_policy(db,workspace_id="default"):
    p=db.scalar(select(PolicyVersion).where(PolicyVersion.workspace_id==workspace_id,PolicyVersion.policy_id=="refund-policy",PolicyVersion.active.is_(True)).order_by(PolicyVersion.row_id.desc()).limit(1))
    return policy_to_dict(p) if p else create_policy(db,workspace_id,policy_id="refund-policy",name="Refund authority",version="17.3",rule={"type":"amount_threshold","field":"amount","auto_approve_max":500,"hard_limit":1500,"currency":"USD"},active=True)

def list_policies(db,workspace_id): return [policy_to_dict(r) for r in db.scalars(select(PolicyVersion).where(PolicyVersion.workspace_id==workspace_id).order_by(PolicyVersion.row_id.desc()))]

def get_active_policy(db,workspace_id,policy_id):
    p=db.scalar(select(PolicyVersion).where(PolicyVersion.workspace_id==workspace_id,PolicyVersion.policy_id==policy_id,PolicyVersion.active.is_(True)).order_by(PolicyVersion.row_id.desc()).limit(1)); return policy_to_dict(p) if p else None

def evaluate_policy(policy,proposed_action,authority=None,context=None):
    rule=policy.get("rule") or {}
    common={
        "policy_id":policy["policy_id"],"version":policy["version"],"policy_digest":policy.get("policy_digest") or policy_digest(policy.get("workspace_id","default"),policy["policy_id"],policy["version"],rule),
        "input_commitment":sha256_hex(canonical_json({"proposed_action":proposed_action or {},"authority":authority or {},"context":context or {}})),
    }
    if rule.get("type")!="amount_threshold": return {**common,"decision":"manual_review_required","reason":"unsupported_policy_rule","rule":rule}
    amount=proposed_action.get(rule.get("field","amount"))
    if not isinstance(amount,(int,float)): return {**common,"decision":"manual_review_required","reason":"amount_missing_or_invalid","rule":rule}
    hard=float(rule.get("hard_limit",0) or 0); auto=float(rule.get("auto_approve_max",0) or 0); authority_limit=(authority or {}).get("limit_usd")
    effective=min(hard,float(authority_limit)) if hard and isinstance(authority_limit,(int,float)) else (hard or float(authority_limit or 0))
    if effective and amount>effective: decision,reason="blocked","action_exceeds_authorized_limit"
    elif amount>auto: decision,reason="human_approval_required","action_exceeds_auto_approval_threshold"
    else: decision,reason="auto_allowed","action_within_auto_approval_threshold"
    return {**common,"decision":decision,"reason":reason,"amount":amount,"human_approval_threshold":auto,"hard_limit":effective or hard,"rule":rule}
