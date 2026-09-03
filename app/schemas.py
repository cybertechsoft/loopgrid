from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict
PrivacyMode=Literal["full","redacted","proof_only"]
KeyScope=Literal["ingest","read","review","admin"]

class WorkspaceCreate(BaseModel):
    name:str=Field(min_length=1,max_length=160,examples=["Acme AI Operations"])
    environment:Literal["development","staging","production"]="development"
    privacy_mode:PrivacyMode="full"
    retention_days:int=Field(default=90,ge=1,le=3650)
    redaction_fields:list[str]=Field(default_factory=list,examples=[["input.customer.email","metadata.internal_case_id"]])
class WorkspaceUpdate(BaseModel):
    privacy_mode:PrivacyMode|None=None;retention_days:int|None=Field(default=None,ge=1,le=3650);redaction_fields:list[str]|None=None
class ApiKeyCreate(BaseModel):
    name:str=Field(default="Default ingestion key",min_length=1,max_length=120)
    description:str=Field(default="",max_length=500)
    scopes:list[KeyScope]=Field(default_factory=lambda:["ingest","read"])
    expires_in_days:int|None=Field(default=None,ge=1,le=3650)
class ApiKeyRotateRequest(BaseModel):
    expires_in_days:int|None=Field(default=None,ge=1,le=3650)
class DecisionCreate(BaseModel):
    decision_type:str=Field(min_length=1,max_length=120,examples=["customer_refund"]);service_name:str=Field(default="ai-agent",max_length=120);workspace_id:str=Field(default="default",max_length=64);privacy_mode:PrivacyMode|None=None;idempotency_key:str|None=Field(default=None,max_length=160);agent:dict[str,Any]=Field(default_factory=dict,examples=[{"id":"support-agent-04","version":"1.8.3"}]);authority:dict[str,Any]=Field(default_factory=dict);model:dict[str,Any]=Field(default_factory=dict,examples=[{"provider":"openai","name":"gpt-5"}]);context:dict[str,Any]=Field(default_factory=dict);input:dict[str,Any]=Field(default_factory=dict);proposed_action:dict[str,Any]=Field(default_factory=dict,examples=[{"tool":"stripe.refunds.create","amount":720,"currency":"USD"}]);metadata:dict[str,Any]=Field(default_factory=dict)
class EventCreate(BaseModel):
    event_type:Literal["model_completed","policy_evaluated","human_approved","human_rejected","tool_requested","tool_result","tool_executed","outcome_observed","human_adjudicated","incident_flagged","replay_executed","checkpoint_created","telemetry_ingested","mcp_tool_requested","mcp_tool_result","payload_erased"]
    actor_type:Literal["agent","human","system","tool","policy","integration"]="system";actor_id:str="loopgrid";payload:dict[str,Any]=Field(default_factory=dict);privacy_mode:PrivacyMode|None=None;idempotency_key:str|None=Field(default=None,max_length=160)
class ReplayRequest(BaseModel):
    mode:Literal["policy","simulation","live"]="policy";policy_threshold:float|None=None;model:str|None=None;prompt:str|None=None;provider:Literal["openai","anthropic"]|None=None
class OTelSpan(BaseModel):
    trace_id:str;span_id:str;name:str;attributes:dict[str,Any]=Field(default_factory=dict);start_time:str|None=None;end_time:str|None=None
class OTelIngest(BaseModel):workspace_id:str="default";spans:list[OTelSpan]
class PolicyCreate(BaseModel):
    policy_id:str=Field(min_length=1,max_length=96);name:str=Field(min_length=1,max_length=160);version:str=Field(min_length=1,max_length=48);rule:dict[str,Any];active:bool=True
class PolicyEvaluate(BaseModel):policy_id:str;proposed_action:dict[str,Any];authority:dict[str,Any]=Field(default_factory=dict);context:dict[str,Any]=Field(default_factory=dict)
class ReviewRequest(BaseModel):action:Literal["approve","reject"];reviewer:str=Field(min_length=1,max_length=160);reason:str=Field(default="",max_length=1000)
class MCPIngest(BaseModel):
    workspace_id:str="default";trace_id:str|None=None;service_name:str="mcp-client";agent_id:str="mcp-agent";server_name:str="mcp-server";request:dict[str,Any];response:dict[str,Any]|None=None;privacy_mode:PrivacyMode|None=None
class ErasePayloadRequest(BaseModel):reason:str=Field(default="customer_request",max_length=160)

# Response models. These intentionally preserve extensibility for evidence payloads while
# making OpenAPI useful to SDK/customer engineers instead of showing anonymous strings.
class HealthResponse(BaseModel):
    ok:bool;service:str;version:str;evidence_profile:str;uptime_seconds:float
class ReadyResponse(BaseModel):
    ready:bool;database:str;signer:str;payload_vault:str;timestamping:str;version:str
class WorkspaceResponse(BaseModel):
    workspace_id:str;name:str;environment:str;privacy_mode:PrivacyMode;retention_days:int;redaction_fields:list[str];created_at:str
class DashboardResponse(BaseModel):
    workspace_id:str;workspace_name:str;privacy_mode:str;decisions:int;events:int;integrity_valid:bool;human_approvals:int;human_rejections:int=0;completed_reviews:int=0;pending_reviews:int;policy_blocks:int;outcomes:dict[str,int];outcome_verified:int;auto_allowed:int;average_evidence_coverage:int;key_id:str|None=None
class ApiKeyIssued(BaseModel):
    key_id:str;name:str;workspace_id:str;scopes:list[str];api_key:str;warning:str
class IntegrityResponse(BaseModel):
    valid:bool;checked_events:int;total_ledger_events:int;failures:list[dict[str,Any]];key_id:str;signature_algorithm:str;signer_provider:str;workspace_id:str|None=None;algorithm:str;chain_scope:str
class DecisionResult(BaseModel):
    model_config=ConfigDict(extra="allow")
    decision_id:str
    event:dict[str,Any]|None=None
    idempotent_replay:bool|None=None
class DecisionDetail(BaseModel):
    summary:dict[str,Any];events:list[dict[str,Any]];verification:dict[str,Any];coverage:dict[str,Any]
class IngestResult(BaseModel):
    accepted:int=0;decision_ids:list[str]=Field(default_factory=list)
class CheckpointResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    workspace_id:str;status:str|None=None;checkpoint_id:str|None=None;ledger_seq:int|None=None;chain_hash:str|None=None;signature:str|None=None;key_id:str|None=None;signature_algorithm:str|None=None;external_timestamp:bool=False
class RetentionResult(BaseModel):workspace_id:str;erased_payloads:int;ledger_integrity_valid:bool
class SystemInfoResponse(BaseModel):
    version:str;evidence_profile:str;stage:str;environment:str;database:dict[str,Any];signer:dict[str,Any];payload_vault:dict[str,Any];timestamping:dict[str,Any];mcp_proxy:dict[str,Any];lifecycle:dict[str,Any];deployment_security:dict[str,Any]=Field(default_factory=dict)

class PilotReadinessCheck(BaseModel):
    id:str;status:Literal["pass","warning","info","not_tested"];required_for_controlled_pilot:bool;message:str;detail:str|None=None
class PilotReadinessResponse(BaseModel):
    version:str;environment:str;controlled_pilot_ready:bool;production_ready:bool;overall:str;checks:list[PilotReadinessCheck]

class BootstrapUserRequest(BaseModel):
    email:str=Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",examples=["founder@acme.ai"])
    display_name:str=Field(min_length=1,max_length=160,examples=["Acme Admin"])
    password:str=Field(min_length=10,max_length=256)
    workspace_id:str="default"
    bootstrap_token:str|None=None
class LoginRequest(BaseModel):
    email:str;password:str;workspace_id:str="default"
class UserCreateRequest(BaseModel):
    email:str;display_name:str;password:str=Field(min_length=10,max_length=256)
class MembershipRequest(BaseModel):
    user_id:str;role:Literal["owner","admin","reviewer","viewer"]
class AuthSessionResponse(BaseModel):
    token:str;token_type:str="bearer";expires_at:str;workspace_id:str;user:dict[str,Any];role:str

# Additional API documentation response contracts. These stay intentionally flexible around
# evidence payloads, while ensuring OpenAPI shows useful structured objects instead of `string`.
class OkResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    ok:bool=True

class HumanPrincipalResponse(BaseModel):
    user_id:str;email:str;display_name:str;workspace_id:str;role:str;scopes:list[str]

class MemberResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    user_id:str;email:str;display_name:str|None=None;role:str;created_at:str|None=None

class ApiKeyMetadataResponse(BaseModel):
    key_id:str;name:str;description:str="";prefix:str;scopes:list[str];created_at:str|None=None;created_by:str|None=None;expires_at:str|None=None;last_used_at:str|None=None;revoked:bool;expired:bool=False;status:str="active";rotated_from_key_id:str|None=None
class ApiKeyRotateResponse(BaseModel):
    old_key_id:str;new_key_id:str;workspace_id:str;scopes:list[str];api_key:str;expires_at:str|None=None;warning:str

class UsageSummaryResponse(BaseModel):
    workspace_id:str;billing_unit:str;billable_decisions:int;totals:dict[str,int];note:str

class AuditEntryResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    audit_id:int;workspace_id:str;actor:str;action:str;target_type:str;target_id:str;detail:dict[str,Any];created_at:str

class PolicyResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    workspace_id:str|None=None;policy_id:str;name:str;version:str;rule:dict[str,Any];policy_digest:str;active:bool;created_at:str|None=None

class PolicyEvaluationResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    policy_id:str;version:str;decision:str;reason:str;policy_digest:str;input_commitment:str

class DecisionSummaryResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    decision_id:str;workspace_id:str;privacy_mode:str;decision_type:str;created_at:str
    agent:dict[str,Any]=Field(default_factory=dict);proposed_action:dict[str,Any]=Field(default_factory=dict)
    policy:dict[str,Any]|None=None;approval:dict[str,Any]|None=None;outcome:dict[str,Any]|None=None;lifecycle:dict[str,Any]|None=None

class LedgerEventResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    event_id:str;decision_id:str;workspace_id:str;seq:int;event_type:str;occurred_at:str

class ReviewItemResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    decision_id:str;decision_type:str;created_at:str;agent:dict[str,Any]|None=None;action:dict[str,Any]|None=None;policy:dict[str,Any]

class ReviewResultResponse(BaseModel):
    decision_id:str;review:dict[str,Any];state:str

class ReplayResultResponse(BaseModel):
    model_config=ConfigDict(extra="allow")

class MCPIngestResponse(BaseModel):
    decision_id:str;idempotent_replay:bool;protocol:str

class OTLPAcceptResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    partialSuccess:dict[str,Any]=Field(default_factory=dict);loopgrid:dict[str,Any]

class PayloadEventStatusResponse(BaseModel):
    event_id:str;event_type:str;privacy_mode:str;payload:dict[str,Any]
class PayloadStatusResponse(BaseModel):
    decision_id:str;events:list[PayloadEventStatusResponse]
class PayloadEraseResponse(BaseModel):
    decision_id:str;erased_payloads:int;ledger_integrity_valid:bool
