from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, Text, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def utcnow(): return datetime.now(timezone.utc)

class Workspace(Base):
    __tablename__="workspaces"
    workspace_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    name:Mapped[str]=mapped_column(String(160),nullable=False)
    environment:Mapped[str]=mapped_column(String(32),nullable=False,default="development")
    privacy_mode:Mapped[str]=mapped_column(String(32),nullable=False,default="full")
    retention_days:Mapped[int]=mapped_column(Integer,nullable=False,default=90)
    redaction_fields_json:Mapped[str]=mapped_column(Text,nullable=False,default="[]")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)

class ApiKey(Base):
    __tablename__="api_keys"
    key_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    name:Mapped[str]=mapped_column(String(120),nullable=False)
    description:Mapped[str]=mapped_column(String(500),nullable=False,default="")
    key_prefix:Mapped[str]=mapped_column(String(20),nullable=False)
    key_hash:Mapped[str]=mapped_column(String(64),nullable=False,unique=True)
    scopes:Mapped[str]=mapped_column(String(240),nullable=False,default="ingest,read")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    created_by:Mapped[str]=mapped_column(String(160),nullable=False,default="system")
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    last_used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    rotated_from_key_id:Mapped[str|None]=mapped_column(String(64),nullable=True)


class UsageEvent(Base):
    __tablename__="usage_events"
    usage_id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    category:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    quantity:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    decision_id:Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    metadata_json:Mapped[str]=mapped_column(Text,nullable=False,default="{}")
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow,index=True)

class PolicyVersion(Base):
    __tablename__="policy_versions"
    row_id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    policy_id:Mapped[str]=mapped_column(String(96),nullable=False,index=True)
    name:Mapped[str]=mapped_column(String(160),nullable=False)
    version:Mapped[str]=mapped_column(String(48),nullable=False)
    rule_json:Mapped[str]=mapped_column(Text,nullable=False)
    active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    __table_args__=(UniqueConstraint("workspace_id","policy_id","version",name="uq_policy_version"),)

class AuditLog(Base):
    __tablename__="audit_logs"
    audit_id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    actor:Mapped[str]=mapped_column(String(160),nullable=False,default="system")
    action:Mapped[str]=mapped_column(String(96),nullable=False,index=True)
    target_type:Mapped[str]=mapped_column(String(64),nullable=False,default="workspace")
    target_id:Mapped[str]=mapped_column(String(160),nullable=False,default="")
    detail_json:Mapped[str]=mapped_column(Text,nullable=False,default="{}")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)


class UserAccount(Base):
    __tablename__="user_accounts"
    user_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    email:Mapped[str]=mapped_column(String(240),nullable=False,unique=True,index=True)
    display_name:Mapped[str]=mapped_column(String(160),nullable=False)
    password_hash:Mapped[str]=mapped_column(Text,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    disabled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class WorkspaceMembership(Base):
    __tablename__="workspace_memberships"
    membership_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    user_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    role:Mapped[str]=mapped_column(String(32),nullable=False,default="viewer")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    __table_args__=(UniqueConstraint("workspace_id","user_id",name="uq_workspace_user"),)

class UserSession(Base):
    __tablename__="user_sessions"
    session_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    token_hash:Mapped[str]=mapped_column(String(64),nullable=False,unique=True,index=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,index=True)
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class PayloadBlob(Base):
    __tablename__="payload_blobs"
    payload_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    event_id:Mapped[str]=mapped_column(String(64),nullable=False,unique=True,index=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    ciphertext_b64:Mapped[str]=mapped_column(Text,nullable=False)
    nonce_b64:Mapped[str]=mapped_column(String(64),nullable=False)
    payload_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    erased_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    erasure_reason:Mapped[str|None]=mapped_column(String(160),nullable=True)

class CheckpointRecord(Base):
    __tablename__="checkpoints"
    checkpoint_id:Mapped[str]=mapped_column(String(64),primary_key=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    ledger_seq:Mapped[int]=mapped_column(Integer,nullable=False)
    chain_hash:Mapped[str]=mapped_column(String(64),nullable=False)
    signature_b64:Mapped[str]=mapped_column(Text,nullable=False)
    key_id:Mapped[str]=mapped_column(String(128),nullable=False)
    signature_algorithm:Mapped[str]=mapped_column(String(64),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    timestamp_provider:Mapped[str]=mapped_column(String(64),nullable=False,default="local_clock")
    timestamp_status:Mapped[str]=mapped_column(String(64),nullable=False,default="not_configured")
    timestamp_token_b64:Mapped[str|None]=mapped_column(Text,nullable=True)
    external_timestamp:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)

class LedgerEvent(Base):
    __tablename__="ledger_events"
    seq:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    event_id:Mapped[str]=mapped_column(String(64),unique=True,nullable=False,index=True)
    decision_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    workspace_id:Mapped[str]=mapped_column(String(64),nullable=False,default="default",index=True)
    event_type:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    actor_type:Mapped[str]=mapped_column(String(32),nullable=False,default="system")
    actor_id:Mapped[str]=mapped_column(String(128),nullable=False,default="loopgrid")
    # payload_json contains the signed disclosure representation. For privacy_mode=full,
    # raw payload bytes live encrypted in PayloadBlob and can be erased independently.
    payload_json:Mapped[str]=mapped_column(Text,nullable=False)
    privacy_mode:Mapped[str]=mapped_column(String(32),nullable=False,default="full")
    payload_commitment:Mapped[str|None]=mapped_column(String(64),nullable=True)
    content_hash:Mapped[str]=mapped_column(String(64),nullable=False)
    previous_chain_hash:Mapped[str]=mapped_column(String(64),nullable=False)
    chain_hash:Mapped[str]=mapped_column(String(64),nullable=False,unique=True)
    signature_b64:Mapped[str]=mapped_column(Text,nullable=False)
    key_id:Mapped[str]=mapped_column(String(128),nullable=False)
    signature_algorithm:Mapped[str]=mapped_column(String(64),nullable=False,default="Ed25519")
    idempotency_key:Mapped[str|None]=mapped_column(String(160),nullable=True)
    __table_args__=(UniqueConstraint("workspace_id","idempotency_key",name="uq_workspace_idempotency"),)

Index("ix_ledger_decision_seq",LedgerEvent.decision_id,LedgerEvent.seq)
Index("ix_ledger_workspace_seq",LedgerEvent.workspace_id,LedgerEvent.seq)
Index("ix_policy_workspace_active",PolicyVersion.workspace_id,PolicyVersion.active)
