from __future__ import annotations
import copy, json, time
import httpx
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request, Body
from fastapi.responses import FileResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import LedgerEvent, Workspace, ApiKey, AuditLog, PolicyVersion, PayloadBlob, CheckpointRecord, UserAccount, WorkspaceMembership, UserSession, UsageEvent
from .schemas import DecisionCreate, EventCreate, ReplayRequest, WorkspaceCreate, WorkspaceUpdate, ApiKeyCreate, ApiKeyRotateRequest, OTelIngest, PolicyCreate, PolicyEvaluate, ReviewRequest, MCPIngest, ErasePayloadRequest, HealthResponse, ReadyResponse, WorkspaceResponse, DashboardResponse, ApiKeyIssued, IntegrityResponse, DecisionResult, DecisionDetail, CheckpointResponse, RetentionResult, SystemInfoResponse, BootstrapUserRequest, LoginRequest, UserCreateRequest, MembershipRequest, AuthSessionResponse, OkResponse, HumanPrincipalResponse, MemberResponse, ApiKeyMetadataResponse, ApiKeyRotateResponse, UsageSummaryResponse, AuditEntryResponse, PolicyResponse, PolicyEvaluationResponse, DecisionSummaryResponse, LedgerEventResponse, ReviewItemResponse, ReviewResultResponse, ReplayResultResponse, MCPIngestResponse, OTLPAcceptResponse, PayloadStatusResponse, PayloadEraseResponse, IngestResult, PilotReadinessResponse
from .service import create_decision, add_event, get_events, list_decisions, summarize_decision, dashboard, evidence_coverage
from .ledger import verify_ledger
from .evidence import build_bundle, render_report
from .replay import policy_replay, live_replay
from .crypto import canonical_json, sha256_hex
from .config import settings, assert_production_safe, production_safety_errors
from .auth import ensure_workspace, create_workspace, create_api_key, authenticate_key, revoke_key, rotate_key, key_scopes, key_status
from .checkpoints import create_checkpoint, latest_checkpoint, checkpoint_to_dict
from .audit import record_audit, list_audit
from .policies import create_policy, list_policies, get_active_policy, evaluate_policy, ensure_refund_policy
from .migrations import migrate_schema
from .version import VERSION,EVIDENCE_PROFILE,PRODUCT_STAGE
from .signing import signer
from .payloads import erase_decision_payloads,erase_expired_payloads,payload_status
from .rate_limit import limiter
from .user_auth import bearer_token_context,current_principal,create_user,add_membership,issue_session,verify_password,authenticate_session,revoke_session
from .usage import usage_summary, record_usage
from .lifecycle import LifecycleError

STARTED=time.time()
assert_production_safe(settings)
Base.metadata.create_all(bind=engine); migrate_schema(engine)

@asynccontextmanager
async def lifespan(app:FastAPI):
    from .db import SessionLocal
    db=SessionLocal()
    try: ensure_workspace(db); ensure_refund_policy(db)
    finally: db.close()
    yield

OPENAPI_TAGS=[
    {"name":"Operations","description":"Health, readiness, metrics and runtime trust posture."},
    {"name":"Workspaces","description":"Tenant/workspace configuration, service identities and administrative audit evidence."},
    {"name":"Policies","description":"Versioned deterministic policy registry and evaluation."},
    {"name":"Decisions","description":"Capture and investigate consequential AI/agent decisions."},
    {"name":"Reviews","description":"Human oversight queue and signed adjudication."},
    {"name":"Ingestion","description":"Native, OpenTelemetry/OTLP and MCP ingestion paths."},
    {"name":"Evidence","description":"Integrity verification, checkpoints, exports and payload-retention controls."},
    {"name":"Replay","description":"Counterfactual and live replay of historic decisions without rewriting production evidence."},
    {"name":"Demo","description":"Local design-partner demo helpers. Disabled or restricted in production deployments."},
]
app=FastAPI(title="LoopGrid Decision Evidence Infrastructure",version=VERSION,description="Verifiable evidence infrastructure for consequential AI and agent decisions. Evidence integrity is not by itself a legal compliance determination.",lifespan=lifespan,openapi_tags=OPENAPI_TAGS)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
        allow_headers=["Authorization","Content-Type","X-LoopGrid-Key","X-LoopGrid-Workspace","X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
STATIC=Path(__file__).parent/"static"; app.mount("/static",StaticFiles(directory=STATIC),name="static")

def _custom_openapi():
    if app.openapi_schema:return app.openapi_schema
    schema=get_openapi(title=app.title,version=app.version,description=app.description,routes=app.routes,tags=OPENAPI_TAGS)
    components=schema.setdefault("components",{});security=components.setdefault("securitySchemes",{})
    security["LoopGridApiKey"]={"type":"apiKey","in":"header","name":"X-LoopGrid-Key","description":"Workspace-scoped service identity. Use ingest/read/review/admin scopes."}
    security["LoopGridUserBearer"]={"type":"http","scheme":"bearer","bearerFormat":"lg_usr_...","description":"Human user session with workspace RBAC."}
    public_paths={"/health","/ready","/metrics","/api/v1/system/info","/api/v1/pilot/readiness","/api/v1/auth/bootstrap","/api/v1/auth/login"}
    for path,item in schema.get("paths",{}).items():
        if path in public_paths or path.startswith("/api/v1/demo/"):continue
        for method,op in item.items():
            if method.lower() in {"get","post","put","patch","delete"}:op.setdefault("security",[{"LoopGridApiKey":[]},{"LoopGridUserBearer":[]}])
    app.openapi_schema=schema;return schema
app.openapi=_custom_openapi

@app.middleware("http")
async def response_hardening(request:Request,call_next):
    rid=request.headers.get("X-Request-ID") or f"req_{uuid4().hex[:20]}"
    token=bearer_token_context.set(request.headers.get("Authorization"))
    path=request.url.path
    content_length=request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length)>settings.max_request_body_bytes:
                bearer_token_context.reset(token)
                return Response(json.dumps({"detail":"Request body too large","max_bytes":settings.max_request_body_bytes}),status_code=413,media_type="application/json",headers={"X-Request-ID":rid})
        except ValueError:
            pass
    if request.method in {"POST","PUT","PATCH","DELETE"}:
        is_ingest=path.startswith(("/api/v1/decisions","/api/v1/ingest","/v1/traces","/api/v1/mcp-proxy"))
        limit=settings.ingest_rate_limit_per_minute if is_ingest else settings.admin_rate_limit_per_minute
        raw=request.headers.get("X-LoopGrid-Key") or (request.client.host if request.client else "unknown")
        identity=sha256_hex(raw.encode())[:16]
        ok,retry=limiter.allow(f"{identity}:{'ingest' if is_ingest else 'admin'}",limit)
        if not ok:
            bearer_token_context.reset(token)
            return Response(json.dumps({"detail":"Rate limit exceeded","retry_after_seconds":retry}),status_code=429,media_type="application/json",headers={"Retry-After":str(retry),"X-Request-ID":rid})
    try:
        response=await call_next(request)
        response.headers["X-Request-ID"]=rid; response.headers["X-Content-Type-Options"]="nosniff"; response.headers["Referrer-Policy"]="no-referrer"; response.headers["X-Frame-Options"]="DENY"; response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
        if request.url.path=="/" or request.url.path.startswith("/api/") or request.url.path in {"/v1/traces","/metrics"}:
            response.headers["Cache-Control"]="no-store"
        # During local/design-partner testing, never let a stale JS/CSS asset survive a build switch.
        if settings.environment!="production" and request.url.path.startswith("/static/"):
            response.headers["Cache-Control"]="no-store, max-age=0"
        return response
    finally:
        # ContextVars are request-local but must always be restored, including exception paths.
        bearer_token_context.reset(token)

def _auth(db,raw,workspace_id=None,*,scope="read",allow_demo=True):
    # Service identities use X-LoopGrid-Key. Human users may use Authorization: Bearer lg_usr_...
    # Both resolve to the same scope model. Supplying an invalid/under-scoped service key never
    # falls through to the local-demo bypass.
    if raw:
        key=authenticate_key(db,raw,scope)
        if key:
            if workspace_id and key.workspace_id!=workspace_id:raise HTTPException(403,"API key does not belong to this workspace")
            return key
        principal=current_principal(db,workspace_id,scope)
        if principal:return principal
        raise HTTPException(401,f"Invalid, revoked, or insufficient LoopGrid API key ({scope} scope required)")
    principal=current_principal(db,workspace_id,scope)
    if principal:return principal
    if bearer_token_context.get():
        raise HTTPException(401,f"Invalid, expired, or insufficient human session ({scope} scope required)")
    if allow_demo and settings.environment!="production" and not settings.require_user_auth:return None
    raise HTTPException(401,f"Missing or insufficient LoopGrid credential ({scope} scope required)")
def _actor(key):return key.key_id if key else "local-demo"
def _workspace_json(w):
    try:fields=json.loads(w.redaction_fields_json or "[]")
    except Exception:fields=[]
    return {"workspace_id":w.workspace_id,"name":w.name,"environment":w.environment,"privacy_mode":w.privacy_mode,"retention_days":w.retention_days,"redaction_fields":fields,"created_at":w.created_at.isoformat()}

@app.get("/",include_in_schema=False)
def home():return FileResponse(STATIC/"index.html")
@app.get("/health",response_model=HealthResponse,tags=["Operations"],summary="Liveness probe")
def health():return {"ok":True,"service":"loopgrid","version":VERSION,"evidence_profile":EVIDENCE_PROFILE,"uptime_seconds":round(time.time()-STARTED,1)}
@app.get("/ready",response_model=ReadyResponse,tags=["Operations"],summary="Readiness and trust-boundary probe")
def ready(db:Session=Depends(get_db)):
    try:
        db.scalar(select(func.count()).select_from(Workspace))
        return {"ready":True,"database":"ok","signer":signer.provider,"payload_vault":"aes-256-gcm","timestamping":"rfc3161" if settings.tsa_url else "not_configured","version":VERSION}
    except Exception as e:raise HTTPException(503,f"Not ready: {type(e).__name__}")
@app.get("/metrics",response_class=PlainTextResponse,tags=["Operations"],summary="Prometheus-style operational metrics")
def metrics(db:Session=Depends(get_db)):
    ws=db.scalar(select(func.count()).select_from(Workspace)) or 0;dec=db.scalar(select(func.count()).select_from(LedgerEvent).where(LedgerEvent.event_type=="decision_created")) or 0;ev=db.scalar(select(func.count()).select_from(LedgerEvent)) or 0;au=db.scalar(select(func.count()).select_from(AuditLog)) or 0;pl=db.scalar(select(func.count()).select_from(PayloadBlob).where(PayloadBlob.erased_at.is_(None))) or 0;cp=db.scalar(select(func.count()).select_from(CheckpointRecord)) or 0;ue=db.scalar(select(func.coalesce(func.sum(UsageEvent.quantity),0)).where(UsageEvent.category=="decision")) or 0
    return f"# HELP loopgrid_workspaces_total Number of workspaces\n# TYPE loopgrid_workspaces_total gauge\nloopgrid_workspaces_total {ws}\n# HELP loopgrid_decisions_total Number of recorded decisions\n# TYPE loopgrid_decisions_total gauge\nloopgrid_decisions_total {dec}\n# HELP loopgrid_events_total Number of signed ledger events\n# TYPE loopgrid_events_total gauge\nloopgrid_events_total {ev}\n# HELP loopgrid_audit_events_total Number of administrative audit records\n# TYPE loopgrid_audit_events_total gauge\nloopgrid_audit_events_total {au}\n# HELP loopgrid_payload_blobs_available Encrypted disclosure payloads currently available\n# TYPE loopgrid_payload_blobs_available gauge\nloopgrid_payload_blobs_available {pl}\n# HELP loopgrid_checkpoints_total Signed workspace checkpoints\n# TYPE loopgrid_checkpoints_total gauge\nloopgrid_checkpoints_total {cp}\n# HELP loopgrid_billable_decisions_total Metered consequential decision records\n# TYPE loopgrid_billable_decisions_total counter\nloopgrid_billable_decisions_total {ue}\n"

@app.get("/api/v1/system/info",response_model=SystemInfoResponse,tags=["Operations"],summary="Runtime trust posture and production capabilities")
def system_info():
    db_kind="postgresql" if settings.database_url.startswith("postgres") else "sqlite"
    return {"version":VERSION,"evidence_profile":EVIDENCE_PROFILE,"stage":PRODUCT_STAGE,"environment":settings.environment,"database":{"provider":db_kind,"pool_pre_ping":True,"target_for_external_pilot":"postgresql"},"signer":signer.posture(),"payload_vault":{"algorithm":"AES-256-GCM","separate_from_signed_ledger":True,"erasable_without_breaking_chain":True,"key_source":"environment" if settings.payload_master_key_b64 else "local_file"},"timestamping":{"provider":"rfc3161" if settings.tsa_url else "not_configured","tsa_url_configured":bool(settings.tsa_url),"trust_note":"TSA imprint is checked at capture. Offline verifier can validate signer trust with --tsa-ca-file."},"mcp_proxy":{"enabled":bool(settings.mcp_upstreams),"configured_aliases":sorted(settings.mcp_upstreams)},"lifecycle":{"enforced":settings.enforce_lifecycle,"model":"append-only deterministic state projection"},"deployment_security":{"strict_production_safety":settings.strict_production_safety,"human_auth_required":settings.require_user_auth,"cors_origins":list(settings.cors_origins),"unsafe_configuration":production_safety_errors(settings)}}

@app.get("/api/v1/pilot/readiness",response_model=PilotReadinessResponse,tags=["Operations"],summary="Controlled-pilot readiness and production gaps")
def pilot_readiness(db:Session=Depends(get_db)):
    checks=[]
    def add(id,status,required,message,detail=None):checks.append({"id":id,"status":status,"required_for_controlled_pilot":required,"message":message,"detail":detail})
    try:
        db.scalar(select(func.count()).select_from(Workspace));add("database","pass",True,"Database connection is healthy", "PostgreSQL" if settings.database_url.startswith("postgres") else "SQLite local evaluation")
    except Exception as e:add("database","warning",True,"Database health check failed",type(e).__name__)
    add("signed_ledger","pass",True,"Signed workspace evidence ledger is enabled",f"{signer.algorithm} / SHA-256")
    add("lifecycle_enforcement","pass" if settings.enforce_lifecycle else "warning",True,"Consequential event ordering is enforced" if settings.enforce_lifecycle else "Lifecycle enforcement is disabled","Blocks execution before required approval and other impossible transitions")
    add("payload_vault","pass",True,"Encrypted disclosure vault is enabled","AES-256-GCM")
    add("api_auth","pass" if settings.require_user_auth else "warning",False,"Human authentication is enforced" if settings.require_user_auth else "Local no-auth UI bypass is enabled","Set LOOPGRID_REQUIRE_USER_AUTH=true for external access")
    safety_errors=production_safety_errors(settings)
    add("deployment_safety","pass" if not safety_errors else "warning",settings.environment=="production","Production safety guard is satisfied" if not safety_errors else "Production safety guard reports blocking configuration", "; ".join(safety_errors) if safety_errors else "Strong bootstrap/admin secrets, auth-required mode, PostgreSQL and non-wildcard CORS")
    add("signer_boundary","pass" if signer.posture().get("hardware_backed") else "warning",False,"Signer is hardware-backed" if signer.posture().get("hardware_backed") else "Local file-backed signer is active","Use AWS KMS for a production trust boundary")
    external_cp=db.scalar(select(CheckpointRecord).where(CheckpointRecord.external_timestamp.is_(True)).order_by(CheckpointRecord.created_at.desc()).limit(1))
    if external_cp:
        add("external_timestamp","pass",False,"A successful externally timestamped checkpoint has been observed",f"{external_cp.checkpoint_id} / ledger_seq={external_cp.ledger_seq}")
    elif settings.tsa_url:
        add("external_timestamp","warning",False,"RFC 3161 TSA is configured but no successful external timestamp has been observed yet","Create a checkpoint and confirm external_timestamp=true")
    else:
        add("external_timestamp","warning",False,"No external timestamp authority configured","Local checkpoints remain signed but are not independently time-attested")
    add("database_topology","pass" if settings.database_url.startswith("postgres") else "warning",False,"PostgreSQL backend configured" if settings.database_url.startswith("postgres") else "SQLite backend configured","Use PostgreSQL for a multi-instance/customer pilot")
    add("mcp_proxy","info" if not settings.mcp_upstreams else "pass",False,"MCP proxy aliases configured" if settings.mcp_upstreams else "MCP proxy optional and currently disabled",", ".join(sorted(settings.mcp_upstreams)) or None)
    controlled=all(c["status"]=="pass" for c in checks if c["required_for_controlled_pilot"])
    production=controlled and all(c["status"]=="pass" for c in checks if c["id"] in {"api_auth","signer_boundary","external_timestamp","database_topology"})
    return {"version":VERSION,"environment":settings.environment,"controlled_pilot_ready":controlled,"production_ready":production,"overall":"CONTROLLED PILOT READY" if controlled else "PILOT BLOCKED","checks":checks}

# human identity / RBAC
@app.post("/api/v1/auth/bootstrap",response_model=AuthSessionResponse,tags=["Workspaces"],summary="Bootstrap the first owner account")
def auth_bootstrap(req:BootstrapUserRequest,db:Session=Depends(get_db)):
    existing=db.scalar(select(func.count()).select_from(UserAccount)) or 0
    if existing:raise HTTPException(409,"Bootstrap is only available before the first user exists")
    if settings.environment=="production" and (not settings.bootstrap_token or req.bootstrap_token!=settings.bootstrap_token):raise HTTPException(401,"Valid LOOPGRID_BOOTSTRAP_TOKEN required")
    ensure_workspace(db,req.workspace_id)
    try:u=create_user(db,req.email,req.display_name,req.password);m=add_membership(db,req.workspace_id,u.user_id,"owner");ses,token,_=issue_session(db,u,req.workspace_id)
    except ValueError as e:raise HTTPException(409,str(e))
    record_audit(db,req.workspace_id,"user.bootstrap_owner",actor=f"user:{u.user_id}",target_type="user",target_id=u.user_id,detail={"email":u.email,"role":"owner"})
    return {"token":token,"token_type":"bearer","expires_at":ses.expires_at.isoformat(),"workspace_id":req.workspace_id,"user":{"user_id":u.user_id,"email":u.email,"display_name":u.display_name},"role":"owner"}

@app.post("/api/v1/auth/login",response_model=AuthSessionResponse,tags=["Workspaces"],summary="Create human user session")
def auth_login(req:LoginRequest,db:Session=Depends(get_db)):
    u=db.scalar(select(UserAccount).where(UserAccount.email==req.email.strip().lower()))
    if not u or u.disabled_at or not verify_password(req.password,u.password_hash):raise HTTPException(401,"Invalid email or password")
    try:ses,token,m=issue_session(db,u,req.workspace_id)
    except ValueError as e:raise HTTPException(403,str(e))
    record_audit(db,req.workspace_id,"user.login",actor=f"user:{u.user_id}",target_type="session",target_id=ses.session_id)
    return {"token":token,"token_type":"bearer","expires_at":ses.expires_at.isoformat(),"workspace_id":req.workspace_id,"user":{"user_id":u.user_id,"email":u.email,"display_name":u.display_name},"role":m.role}

@app.get("/api/v1/auth/me",response_model=HumanPrincipalResponse,tags=["Workspaces"],summary="Current human principal")
def auth_me(db:Session=Depends(get_db)):
    p=current_principal(db)
    if not p:raise HTTPException(401,"Bearer user session required")
    u=db.get(UserAccount,p.user_id);return {"user_id":p.user_id,"email":p.email,"display_name":u.display_name if u else p.email,"workspace_id":p.workspace_id,"role":p.role,"scopes":sorted(p.scopes)}

@app.post("/api/v1/auth/logout",response_model=OkResponse,tags=["Workspaces"],summary="Revoke current human session")
def auth_logout(db:Session=Depends(get_db)):
    p=current_principal(db)
    if not p:raise HTTPException(401,"Bearer user session required")
    revoke_session(db,p);record_audit(db,p.workspace_id,"user.logout",actor=f"user:{p.user_id}",target_type="session",target_id=p.session_id);return {"ok":True}

@app.get("/api/v1/workspaces/{workspace_id}/members",response_model=list[MemberResponse],tags=["Workspaces"],summary="List human workspace members")
def list_members(workspace_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    _auth(db,x_loopgrid_key,workspace_id,scope="admin")
    rows=db.execute(select(WorkspaceMembership,UserAccount).join(UserAccount,WorkspaceMembership.user_id==UserAccount.user_id).where(WorkspaceMembership.workspace_id==workspace_id)).all()
    return [{"user_id":u.user_id,"email":u.email,"display_name":u.display_name,"role":m.role,"created_at":m.created_at.isoformat()} for m,u in rows]

@app.post("/api/v1/workspaces/{workspace_id}/members",response_model=MemberResponse,tags=["Workspaces"],summary="Add or change workspace member role")
def put_member(workspace_id:str,req:MembershipRequest,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    actor=_auth(db,x_loopgrid_key,workspace_id,scope="admin");u=db.get(UserAccount,req.user_id)
    if not u:raise HTTPException(404,"User not found")
    try:m=add_membership(db,workspace_id,u.user_id,req.role)
    except ValueError as e:raise HTTPException(422,str(e))
    record_audit(db,workspace_id,"membership.updated",actor=_actor(actor),target_type="user",target_id=u.user_id,detail={"role":req.role});return {"user_id":u.user_id,"email":u.email,"role":m.role}

@app.post("/api/v1/workspaces/{workspace_id}/members/create-user",response_model=MemberResponse,tags=["Workspaces"],summary="Create local user and add to workspace")
def create_member_user(workspace_id:str,req:UserCreateRequest,role:str=Query("viewer",pattern="^(owner|admin|reviewer|viewer)$"),x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    actor=_auth(db,x_loopgrid_key,workspace_id,scope="admin")
    try:u=create_user(db,req.email,req.display_name,req.password);m=add_membership(db,workspace_id,u.user_id,role)
    except ValueError as e:raise HTTPException(409,str(e))
    record_audit(db,workspace_id,"user.created",actor=_actor(actor),target_type="user",target_id=u.user_id,detail={"email":u.email,"role":role});return {"user_id":u.user_id,"email":u.email,"display_name":u.display_name,"role":m.role}

# workspace/access
@app.get("/api/v1/dashboard",response_model=DashboardResponse,tags=["Workspaces"],summary="Workspace evidence posture")
def get_dashboard(workspace_id:str="default",x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):_auth(db,x_loopgrid_key,workspace_id,scope="read");return dashboard(db,workspace_id)
@app.get("/api/v1/workspaces",response_model=list[WorkspaceResponse],tags=["Workspaces"],summary="List workspaces")
def get_workspaces(x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    if settings.environment=="production":_auth(db,x_loopgrid_key,scope="read",allow_demo=False)
    return [_workspace_json(w) for w in db.scalars(select(Workspace).order_by(Workspace.created_at))]
@app.post("/api/v1/workspaces",response_model=WorkspaceResponse,tags=["Workspaces"],summary="Create workspace")
def post_workspace(req:WorkspaceCreate,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    if settings.environment=="production":
        if x_loopgrid_key!=settings.api_key:raise HTTPException(401,"Platform admin key required")
        actor="platform-admin"
    else:
        actor=_actor(_auth(db,x_loopgrid_key,scope="admin")) if (x_loopgrid_key or settings.require_user_auth) else "local-demo"
    w=create_workspace(db,req.name,req.environment,req.privacy_mode,req.retention_days,req.redaction_fields);record_audit(db,w.workspace_id,"workspace.created",actor=actor,target_type="workspace",target_id=w.workspace_id,detail={"environment":w.environment});return _workspace_json(w)
@app.patch("/api/v1/workspaces/{workspace_id}",response_model=WorkspaceResponse,tags=["Workspaces"],summary="Update workspace privacy and retention")
def patch_workspace(workspace_id:str,req:WorkspaceUpdate,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    key=_auth(db,x_loopgrid_key,workspace_id,scope="admin");w=db.get(Workspace,workspace_id)
    if not w:raise HTTPException(404,"Workspace not found")
    data=req.model_dump(exclude_none=True)
    if "privacy_mode" in data:w.privacy_mode=data["privacy_mode"]
    if "retention_days" in data:w.retention_days=data["retention_days"]
    if "redaction_fields" in data:w.redaction_fields_json=json.dumps(data["redaction_fields"])
    db.commit();db.refresh(w);record_audit(db,workspace_id,"workspace.settings_updated",actor=_actor(key),target_type="workspace",target_id=workspace_id,detail=data);return _workspace_json(w)
@app.post("/api/v1/workspaces/{workspace_id}/keys",response_model=ApiKeyIssued,tags=["Workspaces"],summary="Issue scoped service API key")
def post_key(workspace_id:str,req:ApiKeyCreate,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    # API-key issuance is an administrative action. The platform-admin key remains
    # available for controlled production bootstrap, while normal callers must pass
    # the same admin authorization boundary used by all other workspace admin routes.
    if settings.environment=="production" and x_loopgrid_key==settings.api_key:
        key=None
        actor="platform-admin"
    else:
        key=_auth(db,x_loopgrid_key,workspace_id,scope="admin")
        actor=_actor(key)
    obj,raw=create_api_key(db,workspace_id,req.name,list(req.scopes),description=req.description,expires_in_days=req.expires_in_days,created_by=actor)
    record_audit(db,workspace_id,"api_key.created",actor=actor,target_type="api_key",target_id=obj.key_id,detail={"name":obj.name,"description":obj.description,"scopes":sorted(key_scopes(obj)),"expires_at":obj.expires_at.isoformat() if obj.expires_at else None})
    return {"key_id":obj.key_id,"name":obj.name,"workspace_id":workspace_id,"scopes":sorted(key_scopes(obj)),"api_key":raw,"warning":"This key is shown once. Store it securely."}

@app.get("/api/v1/workspaces/{workspace_id}/keys",response_model=list[ApiKeyMetadataResponse],tags=["Workspaces"],summary="List service API keys")
def list_keys(workspace_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    _auth(db,x_loopgrid_key,workspace_id,scope="admin")
    return [{"key_id":k.key_id,"name":k.name,"description":k.description or "","prefix":k.key_prefix,"scopes":sorted(key_scopes(k)),"created_at":k.created_at.isoformat(),"created_by":k.created_by,"expires_at":k.expires_at.isoformat() if k.expires_at else None,"last_used_at":k.last_used_at.isoformat() if k.last_used_at else None,"revoked":bool(k.revoked_at),"expired":key_status(k)=="expired","status":key_status(k),"rotated_from_key_id":k.rotated_from_key_id} for k in db.scalars(select(ApiKey).where(ApiKey.workspace_id==workspace_id).order_by(ApiKey.created_at.desc()))]

@app.post("/api/v1/workspaces/{workspace_id}/keys/{key_id}/rotate",response_model=ApiKeyRotateResponse,tags=["Workspaces"],summary="Rotate a service API key and revoke the predecessor")
def rotate_service_key(workspace_id:str,key_id:str,req:ApiKeyRotateRequest,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    actor=_auth(db,x_loopgrid_key,workspace_id,scope="admin");old=db.get(ApiKey,key_id)
    if not old or old.workspace_id!=workspace_id:raise HTTPException(404,"API key not found")
    old,new,raw=rotate_key(db,key_id,created_by=_actor(actor),expires_in_days=req.expires_in_days)
    if not new:
        raise HTTPException(409,f"API key cannot be rotated because its status is {key_status(old)}")
    record_audit(db,workspace_id,"api_key.rotated",actor=_actor(actor),target_type="api_key",target_id=new.key_id,detail={"rotated_from":key_id,"scopes":sorted(key_scopes(new)),"expires_at":new.expires_at.isoformat() if new.expires_at else None})
    return {"old_key_id":key_id,"new_key_id":new.key_id,"workspace_id":workspace_id,"scopes":sorted(key_scopes(new)),"api_key":raw,"expires_at":new.expires_at.isoformat() if new.expires_at else None,"warning":"The predecessor is revoked immediately. This replacement key is shown once."}

@app.delete("/api/v1/workspaces/{workspace_id}/keys/{key_id}",response_model=OkResponse,tags=["Workspaces"],summary="Revoke service API key")
def delete_key(workspace_id:str,key_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    key=_auth(db,x_loopgrid_key,workspace_id,scope="admin");obj=db.get(ApiKey,key_id)
    if not obj or obj.workspace_id!=workspace_id:raise HTTPException(404,"API key not found")
    revoke_key(db,key_id);record_audit(db,workspace_id,"api_key.revoked",actor=_actor(key),target_type="api_key",target_id=key_id);return {"ok":True,"key_id":key_id,"revoked":True}

@app.get("/api/v1/workspaces/{workspace_id}/usage",response_model=UsageSummaryResponse,tags=["Workspaces"],summary="Workspace usage meter for pilot pricing and capacity planning")
def get_usage(workspace_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    _auth(db,x_loopgrid_key,workspace_id,scope="read");return usage_summary(db,workspace_id)
@app.get("/api/v1/workspaces/{workspace_id}/audit",response_model=list[AuditEntryResponse],tags=["Workspaces"],summary="Administrative audit trail")
def get_audit(workspace_id:str,limit:int=Query(100,ge=1,le=500),x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):_auth(db,x_loopgrid_key,workspace_id,scope="admin");return list_audit(db,workspace_id,limit)

# policy registry
@app.get("/api/v1/workspaces/{workspace_id}/policies",response_model=list[PolicyResponse],tags=["Policies"],summary="List versioned policies")
def get_policies(workspace_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):_auth(db,x_loopgrid_key,workspace_id,scope="read");return list_policies(db,workspace_id)
@app.post("/api/v1/workspaces/{workspace_id}/policies",response_model=PolicyResponse,tags=["Policies"],summary="Create and optionally activate policy version")
def post_policy(workspace_id:str,req:PolicyCreate,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    key=_auth(db,x_loopgrid_key,workspace_id,scope="admin")
    try:p=create_policy(db,workspace_id,policy_id=req.policy_id,name=req.name,version=req.version,rule=req.rule,active=req.active)
    except Exception as e:db.rollback();raise HTTPException(409,f"Policy version could not be created: {e}")
    record_audit(db,workspace_id,"policy.version_created",actor=_actor(key),target_type="policy",target_id=f"{req.policy_id}:{req.version}",detail={"active":req.active});return p
@app.post("/api/v1/workspaces/{workspace_id}/policies/evaluate",response_model=PolicyEvaluationResponse,tags=["Policies"],summary="Deterministically evaluate proposed action")
def post_policy_evaluate(workspace_id:str,req:PolicyEvaluate,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    _auth(db,x_loopgrid_key,workspace_id,scope="ingest");p=get_active_policy(db,workspace_id,req.policy_id)
    if not p:raise HTTPException(404,"Active policy not found")
    return evaluate_policy(p,req.proposed_action,req.authority,req.context)

# decisions/reviews
@app.post("/api/v1/decisions",response_model=DecisionResult,tags=["Decisions"],summary="Record signed decision evidence")
def post_decision(req:DecisionCreate,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    key=_auth(db,x_loopgrid_key,req.workspace_id,scope="ingest");r=create_decision(db,req.model_dump())
    if not r.get("idempotent_replay"):record_audit(db,req.workspace_id,"decision.ingested",actor=_actor(key),target_type="decision",target_id=r["decision_id"],detail={"decision_type":req.decision_type,"privacy_mode":r["event"].get("privacy_mode")})
    return r
@app.get("/api/v1/decisions",response_model=list[DecisionSummaryResponse],tags=["Decisions"],summary="List decisions")
def get_decisions(limit:int=Query(100,ge=1,le=500),workspace_id:str="default",x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):_auth(db,x_loopgrid_key,workspace_id,scope="read");return list_decisions(db,limit,workspace_id)
@app.get("/api/v1/decisions/{decision_id}",response_model=DecisionDetail,tags=["Decisions"],summary="Investigate a decision")
def get_decision(decision_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    try:events=get_events(db,decision_id)
    except KeyError:raise HTTPException(404,"Decision not found")
    _auth(db,x_loopgrid_key,events[0]["workspace_id"],scope="read");v=verify_ledger(db,decision_id);s=summarize_decision(events);return {"summary":s,"events":events,"verification":v,"coverage":evidence_coverage(s,v)}
@app.post("/api/v1/decisions/{decision_id}/events",response_model=LedgerEventResponse,tags=["Decisions"],summary="Append signed evidence event")
def post_event(decision_id:str,req:EventCreate,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    try:
        first=get_events(db,decision_id)[0];key=_auth(db,x_loopgrid_key,first["workspace_id"],scope="ingest");out=add_event(db,decision_id,req.event_type,req.payload,req.actor_type,req.actor_id,req.privacy_mode,req.idempotency_key);record_audit(db,first["workspace_id"],"decision.event_added",actor=_actor(key),target_type="decision",target_id=decision_id,detail={"event_type":req.event_type});return out
    except KeyError:raise HTTPException(404,"Decision not found")
    except LifecycleError as e:raise HTTPException(409,{"code":e.code,"message":e.message})
@app.get("/api/v1/reviews",response_model=list[ReviewItemResponse],tags=["Reviews"],summary="List decisions awaiting human review")
def get_reviews(workspace_id:str="default",x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    _auth(db,x_loopgrid_key,workspace_id,scope="review");pending=[]
    for d in list_decisions(db,500,workspace_id):
        p=d.get("policy") or {}
        if p.get("decision")=="human_approval_required" and not d.get("approval"):pending.append({"decision_id":d["decision_id"],"decision_type":d["decision_type"],"created_at":d["created_at"],"agent":d.get("agent"),"action":d.get("proposed_action"),"policy":p})
    return pending
@app.post("/api/v1/decisions/{decision_id}/review",response_model=ReviewResultResponse,tags=["Reviews"],summary="Approve or reject with signed oversight evidence")
def post_review(decision_id:str,req:ReviewRequest,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    try:events=get_events(db,decision_id)
    except KeyError:raise HTTPException(404,"Decision not found")
    key=_auth(db,x_loopgrid_key,events[0]["workspace_id"],scope="review");s=summarize_decision(events)
    if s.get("approval"):raise HTTPException(409,"Decision already reviewed")
    if (s.get("policy") or {}).get("decision")!="human_approval_required":raise HTTPException(409,"Decision is not awaiting human approval")
    et="human_approved" if req.action=="approve" else "human_rejected";ev=add_event(db,decision_id,et,{"approved":req.action=="approve","reviewer":req.reviewer,"reason":req.reason},"human",req.reviewer);record_usage(db,events[0]["workspace_id"],"review",1,decision_id=decision_id,metadata={"action":req.action});record_audit(db,events[0]["workspace_id"],f"review.{req.action}",actor=req.reviewer if not key else _actor(key),target_type="decision",target_id=decision_id,detail={"reason":req.reason});return {"decision_id":decision_id,"review":ev,"state":req.action}

# telemetry/protocol capture
@app.post("/api/v1/ingest/otel",response_model=IngestResult,tags=["Ingestion"],summary="Ingest normalized GenAI spans")
def ingest_otel(req:OTelIngest,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    _auth(db,x_loopgrid_key,req.workspace_id,scope="ingest");created=[]
    for span in req.spans:
        a=span.attributes;d=create_decision(db,{"workspace_id":req.workspace_id,"decision_type":a.get("loopgrid.decision.type","genai_operation"),"service_name":a.get("service.name","otel-service"),"idempotency_key":f"otel:{span.trace_id}:{span.span_id}","agent":{"id":a.get("gen_ai.agent.name") or a.get("service.name","unknown-agent")},"model":{"provider":a.get("gen_ai.provider.name"),"name":a.get("gen_ai.request.model") or a.get("gen_ai.response.model")},"context":{"trace_id":span.trace_id,"span_id":span.span_id,"span_name":span.name},"input":{"prompt":a.get("gen_ai.prompt") or a.get("gen_ai.input.messages")},"proposed_action":{"tool":a.get("gen_ai.tool.name")},"metadata":{"source":"opentelemetry","capture_source":"otel-mapping","attributes":a}});created.append(d["decision_id"])
    return {"accepted":len(created),"decision_ids":created,"format":"loopgrid-otel-json"}
def _otlp_value(v):
    if not isinstance(v,dict):return v
    for k in ("stringValue","boolValue","intValue","doubleValue"):
        if k in v:return v[k]
    if "arrayValue" in v:return [_otlp_value(x) for x in v.get("arrayValue",{}).get("values",[])]
    return v
def _otlp_attrs(attrs):return {a.get("key"):_otlp_value(a.get("value",{})) for a in (attrs or []) if a.get("key")}
@app.post("/v1/traces",response_model=OTLPAcceptResponse,tags=["Ingestion"],summary="OTLP/HTTP JSON traces receiver")
async def ingest_otlp_http(request:Request,x_loopgrid_key:str|None=Header(default=None),x_loopgrid_workspace:str|None=Header(default=None),db:Session=Depends(get_db)):
    wid=x_loopgrid_workspace or "default";_auth(db,x_loopgrid_key,wid,scope="ingest");body=await request.json();created=[]
    for rs in body.get("resourceSpans",[]):
        resource=_otlp_attrs((rs.get("resource") or {}).get("attributes",[]))
        for ss in rs.get("scopeSpans",[]):
            for sp in ss.get("spans",[]):
                attrs={**resource,**_otlp_attrs(sp.get("attributes",[]))};trace=sp.get("traceId") or "unknown";sid=sp.get("spanId") or sha256_hex(canonical_json(sp))[:16]
                d=create_decision(db,{"workspace_id":wid,"decision_type":attrs.get("loopgrid.decision.type","genai_operation"),"service_name":attrs.get("service.name","otlp-service"),"idempotency_key":f"otlp:{trace}:{sid}","agent":{"id":attrs.get("gen_ai.agent.name") or attrs.get("service.name","unknown-agent")},"model":{"provider":attrs.get("gen_ai.provider.name") or attrs.get("gen_ai.system"),"name":attrs.get("gen_ai.request.model") or attrs.get("gen_ai.response.model")},"context":{"trace_id":trace,"span_id":sid,"span_name":sp.get("name"),"scope":(ss.get("scope") or {}).get("name")},"input":{},"proposed_action":{"tool":attrs.get("gen_ai.tool.name")},"metadata":{"source":"otlp-http-json","capture_source":"otlp-http-json","attributes":attrs}});created.append(d["decision_id"])
    return {"partialSuccess":{},"loopgrid":{"accepted":len(created),"decision_ids":created}}
@app.post("/api/v1/ingest/mcp",response_model=MCPIngestResponse,tags=["Ingestion"],summary="Capture MCP JSON-RPC tool evidence")
def ingest_mcp(req:MCPIngest,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    _auth(db,x_loopgrid_key,req.workspace_id,scope="ingest");method=req.request.get("method","unknown");params=req.request.get("params") or {};tool=params.get("name") if method=="tools/call" else method;idem=f"mcp:{req.trace_id or sha256_hex(canonical_json(req.request))[:20]}:{req.request.get('id','noid')}"
    d=create_decision(db,{"workspace_id":req.workspace_id,"privacy_mode":req.privacy_mode,"decision_type":"mcp_tool_call","service_name":req.service_name,"idempotency_key":idem,"agent":{"id":req.agent_id},"context":{"trace_id":req.trace_id,"protocol":"MCP","server":req.server_name},"input":{"jsonrpc":req.request.get("jsonrpc"),"method":method,"params":params},"proposed_action":{"tool":tool,"arguments":params.get("arguments")},"metadata":{"source":"mcp-json-rpc","capture_source":"mcp-json-rpc"}});did=d["decision_id"]
    if not d.get("idempotent_replay"):
        add_event(db,did,"mcp_tool_requested",{"server":req.server_name,"method":method,"tool":tool},"integration",req.server_name)
        if req.response is not None:
            add_event(db,did,"mcp_tool_result",{"server":req.server_name,"response":req.response},"integration",req.server_name);status="failed" if req.response.get("error") else "succeeded";add_event(db,did,"outcome_observed",{"status":status,"verified_against":req.server_name,"protocol":"MCP"},"system","mcp-outcome")
    return {"decision_id":did,"idempotent_replay":bool(d.get("idempotent_replay")),"protocol":"MCP"}

@app.post("/api/v1/mcp-proxy/{alias}",tags=["Ingestion"],summary="Configured MCP HTTP proxy with evidence capture")
async def mcp_proxy(alias:str,request:Request,x_loopgrid_key:str|None=Header(default=None),x_loopgrid_workspace:str|None=Header(default=None),db:Session=Depends(get_db)):
    wid=x_loopgrid_workspace or "default";_auth(db,x_loopgrid_key,wid,scope="ingest")
    upstream=settings.mcp_upstreams.get(alias)
    if not upstream:raise HTTPException(404,"MCP upstream alias is not configured. Configure LOOPGRID_MCP_UPSTREAMS_JSON; arbitrary URLs are intentionally rejected.")
    body=await request.json()
    try:
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:r=await client.post(upstream,json=body,headers={"Content-Type":"application/json"})
        try:response_json=r.json()
        except Exception:response_json={"http_status":r.status_code,"body":r.text[:4000]}
    except Exception as e:raise HTTPException(502,f"Configured MCP upstream failed: {type(e).__name__}")
    capture=MCPIngest(workspace_id=wid,trace_id=request.headers.get("traceparent"),service_name=f"mcp-proxy:{alias}",agent_id=request.headers.get("X-LoopGrid-Agent","mcp-agent"),server_name=alias,request=body,response=response_json)
    ingest_mcp(capture,x_loopgrid_key,db)
    return Response(content=json.dumps(response_json),status_code=r.status_code,media_type="application/json")

# replay/evidence
@app.post("/api/v1/decisions/{decision_id}/replay",response_model=ReplayResultResponse,tags=["Replay"],summary="Counterfactual replay without rewriting history")
async def replay(decision_id:str,req:ReplayRequest,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    try:events=get_events(db,decision_id)
    except KeyError:raise HTTPException(404,"Decision not found")
    _auth(db,x_loopgrid_key,events[0]["workspace_id"],scope="ingest");summary=summarize_decision(events);result=await live_replay(summary,req.provider,req.model,req.prompt) if req.mode=="live" else policy_replay(summary,req.policy_threshold);add_event(db,decision_id,"replay_executed",{"request":req.model_dump(),"result":result},"system","replay-engine");return result
@app.get("/api/v1/integrity/verify",response_model=IntegrityResponse,tags=["Evidence"],summary="Verify workspace evidence chain")
def integrity(workspace_id:str="default",x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    _auth(db,x_loopgrid_key,workspace_id,scope="read")
    result=verify_ledger(db,workspace_id=workspace_id)
    record_usage(db,workspace_id,"verification",1,metadata={"scope":"workspace","valid":result.get("valid")})
    return result
@app.get("/api/v1/decisions/{decision_id}/verify",response_model=IntegrityResponse,tags=["Evidence"],summary="Verify decision within workspace chain")
def verify_decision(decision_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    try:first=get_events(db,decision_id)[0]
    except KeyError:raise HTTPException(404,"Decision not found")
    _auth(db,x_loopgrid_key,first["workspace_id"],scope="read")
    result=verify_ledger(db,decision_id)
    record_usage(db,first["workspace_id"],"verification",1,decision_id=decision_id,metadata={"scope":"decision","valid":result.get("valid")})
    return result
@app.get("/api/v1/public-key.pem",tags=["Evidence"],summary="Download active signing public key")
def get_public_key():return Response(signer.public_key_pem(),media_type="application/x-pem-file")
@app.post("/api/v1/workspaces/{workspace_id}/checkpoint",response_model=CheckpointResponse,tags=["Evidence"],summary="Sign chain head and request optional RFC3161 timestamp")
def checkpoint(workspace_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    key=_auth(db,x_loopgrid_key,workspace_id,scope="admin");cp=create_checkpoint(db,workspace_id)
    record_usage(db,workspace_id,"checkpoint",1,metadata={"ledger_seq":cp.get("ledger_seq"),"external_timestamp":cp.get("external_timestamp")})
    record_audit(db,workspace_id,"checkpoint.created",actor=_actor(key),target_type="workspace",target_id=workspace_id,detail={"ledger_seq":cp.get("ledger_seq"),"external_timestamp":cp.get("external_timestamp")});return cp
@app.get("/api/v1/decisions/{decision_id}/evidence",tags=["Evidence"],summary="Export portable independently verifiable evidence bundle")
def evidence(decision_id:str,include_payloads:bool=Query(True,description="Include available decrypted FULL-mode disclosures in disclosures.jsonl. Signed ledger proof is identical either way."),x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    try:
        first=get_events(db,decision_id)[0];_auth(db,x_loopgrid_key,first["workspace_id"],scope="read");data,filename=build_bundle(db,decision_id,include_payloads=include_payloads)
    except KeyError:raise HTTPException(404,"Decision not found")
    record_usage(db,first["workspace_id"],"evidence_export",1,decision_id=decision_id,metadata={"include_payloads":include_payloads,"bytes":len(data)})
    return Response(data,media_type="application/zip",headers={"Content-Disposition":f'attachment; filename="{filename}"'})
@app.get("/api/v1/decisions/{decision_id}/payload-status",response_model=PayloadStatusResponse,tags=["Evidence"],summary="Inspect encrypted disclosure availability")
def decision_payload_status(decision_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    rows=list(db.scalars(select(LedgerEvent).where(LedgerEvent.decision_id==decision_id).order_by(LedgerEvent.seq.asc())))
    if not rows:raise HTTPException(404,"Decision not found")
    _auth(db,x_loopgrid_key,rows[0].workspace_id,scope="read")
    return {"decision_id":decision_id,"events":[{"event_id":e.event_id,"event_type":e.event_type,"privacy_mode":e.privacy_mode,"payload":payload_status(db,e.event_id)} for e in rows]}

@app.post("/api/v1/decisions/{decision_id}/payload/erase",response_model=PayloadEraseResponse,tags=["Evidence"],summary="Erase encrypted full payload disclosures while preserving signed proof")
def erase_payload(decision_id:str,req:ErasePayloadRequest,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    rows=list(db.scalars(select(LedgerEvent).where(LedgerEvent.decision_id==decision_id).order_by(LedgerEvent.seq.asc())))
    if not rows:raise HTTPException(404,"Decision not found")
    key=_auth(db,x_loopgrid_key,rows[0].workspace_id,scope="admin");count=erase_decision_payloads(db,[e.event_id for e in rows],req.reason)
    add_event(db,decision_id,"payload_erased",{"erased_payload_count":count,"reason":req.reason,"proof_preserved":True},"system","retention-engine",privacy_mode="redacted")
    record_audit(db,rows[0].workspace_id,"payload.erased",actor=_actor(key),target_type="decision",target_id=decision_id,detail={"count":count,"reason":req.reason})
    v=verify_ledger(db,workspace_id=rows[0].workspace_id);return {"decision_id":decision_id,"erased_payloads":count,"ledger_integrity_valid":v["valid"]}

@app.post("/api/v1/workspaces/{workspace_id}/retention/run",response_model=RetentionResult,tags=["Evidence"],summary="Apply workspace disclosure retention policy")
def run_retention(workspace_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    key=_auth(db,x_loopgrid_key,workspace_id,scope="admin");count=erase_expired_payloads(db,workspace_id);record_audit(db,workspace_id,"retention.run",actor=_actor(key),target_type="workspace",target_id=workspace_id,detail={"erased_payloads":count});v=verify_ledger(db,workspace_id=workspace_id);return {"workspace_id":workspace_id,"erased_payloads":count,"ledger_integrity_valid":v["valid"]}

@app.get("/api/v1/decisions/{decision_id}/report",tags=["Evidence"],summary="Human-readable evidence report")
def evidence_report(decision_id:str,x_loopgrid_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    try:events=get_events(db,decision_id)
    except KeyError:raise HTTPException(404,"Decision not found")
    _auth(db,x_loopgrid_key,events[0]["workspace_id"],scope="read");s=summarize_decision(events);v=verify_ledger(db,decision_id);return Response(render_report(s,events,v,evidence_coverage(s,v)),media_type="text/html")

# demo
def _demo_guard():
    if settings.environment=="production":
        raise HTTPException(403,"Demo endpoints are disabled in production")

def _append_refund_flow(db,amount,scenario):
    ensure_workspace(db);policy=ensure_refund_policy(db);rule=policy.get("rule") or {};hard=float(rule.get("hard_limit",1500))
    d=create_decision(db,{"workspace_id":"default","decision_type":"customer_refund","service_name":"support-agent","agent":{"id":"support-agent-04","version":"1.8.3","deployment_sha":"demo8a31"},"authority":{"acting_for":"Acme Support","scope":["refund:create"],"limit_usd":hard},"model":{"provider":"demo","name":"support-reasoner","temperature":0.1},"context":{"prompt_version":"support-v14","retrieval_refs":[f"{policy['policy_id']}-v{policy['version']}"]},"input":{"message":f"I was charged twice. Refund the duplicate ${amount}.","customer_ref":f"cust_demo_{amount}"},"proposed_action":{"tool":"stripe.refunds.create","amount":amount,"currency":"USD"},"metadata":{"demo":True,"scenario":scenario,"capture_source":"native-demo"}});did=d["decision_id"]
    add_event(db,did,"model_completed",{"response":f"Duplicate charge detected. Propose refund of ${amount}."},"agent","support-agent-04");result=evaluate_policy(policy,{"amount":amount},{"limit_usd":hard});add_event(db,did,"policy_evaluated",result,"policy",f"{policy['policy_id']}-v{policy['version']}")
    if result["decision"]=="blocked":add_event(db,did,"outcome_observed",{"status":"blocked","verified_against":"policy-engine","amount":amount,"reason":"No external action executed"},"system","outcome-verifier");return did
    if result["decision"]=="human_approval_required":add_event(db,did,"human_approved",{"approved":True,"reviewer":"alice@acme.example","reason":"Duplicate charge verified"},"human","alice@acme.example")
    add_event(db,did,"tool_executed",{"tool":"stripe.refunds.create","request":{"amount":int(amount*100),"currency":"usd"},"sandbox":True,"external_reference":f"re_demo_{amount}"},"tool","stripe-sandbox");add_event(db,did,"outcome_observed",{"status":"succeeded","verified_against":"stripe-sandbox","external_reference":f"re_demo_{amount}","amount":amount},"system","outcome-verifier");return did
def _append_pending_review(db):
    policy=ensure_refund_policy(db);rule=policy.get("rule") or {};auto=float(rule.get("auto_approve_max",500));hard=float(rule.get("hard_limit",1500));amount=int(min(max(auto+220,auto+1),hard-1 if hard>auto+1 else auto+1))
    d=create_decision(db,{"workspace_id":"default","decision_type":"customer_refund","service_name":"support-agent","agent":{"id":"support-agent-04","version":"1.8.3","deployment_sha":"demo8a31"},"authority":{"acting_for":"Acme Support","scope":["refund:create"],"limit_usd":hard},"model":{"provider":"demo","name":"support-reasoner","temperature":0.1},"context":{"prompt_version":"support-v14","retrieval_refs":[f"{policy['policy_id']}-v{policy['version']}"]},"input":{"message":f"Please refund ${amount} for a duplicate charge.","customer_ref":"cust_review_demo"},"proposed_action":{"tool":"stripe.refunds.create","amount":amount,"currency":"USD"},"metadata":{"demo":True,"scenario":"pending_review","capture_source":"native-demo"}});did=d["decision_id"];add_event(db,did,"model_completed",{"response":f"Duplicate charge detected. Propose refund of ${amount}."},"agent","support-agent-04");res=evaluate_policy(policy,{"amount":amount},{"limit_usd":hard});add_event(db,did,"policy_evaluated",res,"policy",f"{policy['policy_id']}-v{policy['version']}");return did
@app.post("/api/v1/demo/refund",tags=["Demo"])
def demo_refund(db:Session=Depends(get_db)):_demo_guard();return get_decision(_append_refund_flow(db,720,"approval"),None,db)
@app.post("/api/v1/demo/pending-review",tags=["Demo"])
def demo_pending_review(db:Session=Depends(get_db)):_demo_guard();return get_decision(_append_pending_review(db),None,db)
@app.post("/api/v1/demo/workspace",tags=["Demo"])
def demo_workspace(db:Session=Depends(get_db)):
    _demo_guard();ids=[_append_refund_flow(db,a,s) for a,s in [(120,"auto"),(720,"approval"),(2400,"blocked")]];return {"created":ids,"count":len(ids),"dashboard":dashboard(db)}
@app.delete("/api/v1/demo/reset",tags=["Demo"])
def demo_reset(db:Session=Depends(get_db)):
    _demo_guard()
    db.execute(delete(PayloadBlob));db.execute(delete(CheckpointRecord));db.execute(delete(UsageEvent));db.execute(delete(LedgerEvent));db.execute(delete(AuditLog));db.execute(delete(PolicyVersion));
    ws=ensure_workspace(db);ws.privacy_mode="full";ws.retention_days=90;ws.redaction_fields_json="[]";db.commit();ensure_refund_policy(db);return {"ok":True,"policy":"refund-policy v17.3","workspace_privacy":"full"}
@app.post("/api/v1/decisions/{decision_id}/tamper-test",tags=["Evidence"],summary="Safe in-memory tamper demonstration")
def tamper_test(decision_id:str,db:Session=Depends(get_db)):
    try:events=get_events(db,decision_id)
    except KeyError:raise HTTPException(404,"Decision not found")
    original=verify_ledger(db,decision_id);altered=copy.deepcopy(events);target=next((e for e in altered if e["event_type"]=="model_completed"),altered[0])
    signed_payload=copy.deepcopy(target.get("signed_payload") or target.get("payload"))
    if isinstance(signed_payload,dict):
        if "payload_sha256" in signed_payload:signed_payload["payload_sha256"]="0"*64
        else:signed_payload["_tamper_demo"]="modified after signing"
    body={k:target.get(k) for k in ["event_id","decision_id","workspace_id","event_type","occurred_at","actor","privacy_mode","payload_commitment"]};body["payload"]=signed_payload;recomputed=sha256_hex(canonical_json(body));proof=target["proof"];reasons=[]
    if recomputed!=proof["content_hash"]:reasons.append("content_hash_mismatch")
    expected=sha256_hex(bytes.fromhex(proof["previous_chain_hash"])+bytes.fromhex(recomputed))
    if expected!=proof["chain_hash"]:reasons.append("chain_hash_mismatch")
    if not signer.verify_hash(proof["chain_hash"],proof["signature"]):reasons.append("signature_invalid")
    return {"production_record_unchanged":True,"original":{"valid":original["valid"],"events":original["checked_events"]},"simulated_tamper":{"valid":not reasons,"detected":bool(reasons),"event_id":target["event_id"],"event_type":target["event_type"],"reasons":reasons}}
