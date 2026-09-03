from __future__ import annotations
import base64,hashlib,hmac,os,secrets
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from .models import UserAccount,WorkspaceMembership,UserSession
from .config import settings

bearer_token_context:ContextVar[str|None]=ContextVar('loopgrid_bearer',default=None)
ROLE_SCOPES={"owner":{"read","ingest","review","admin"},"admin":{"read","ingest","review","admin"},"reviewer":{"read","review"},"viewer":{"read"}}

def _scrypt(password:str,salt:bytes)->bytes:return hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=32)
def hash_password(password:str)->str:
    salt=os.urandom(16);return 'scrypt$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(_scrypt(password,salt)).decode()
def verify_password(password:str,encoded:str)->bool:
    try:
        scheme,salt_b64,digest_b64=encoded.split('$',2);salt=base64.b64decode(salt_b64);expected=base64.b64decode(digest_b64);return scheme=='scrypt' and hmac.compare_digest(_scrypt(password,salt),expected)
    except Exception:return False

def create_user(db:Session,email:str,display_name:str,password:str)->UserAccount:
    email=email.strip().lower()
    if db.scalar(select(UserAccount).where(UserAccount.email==email)):raise ValueError('User already exists')
    u=UserAccount(user_id=f"usr_{uuid4().hex[:18]}",email=email,display_name=display_name.strip() or email,password_hash=hash_password(password));db.add(u);db.commit();db.refresh(u);return u

def add_membership(db:Session,workspace_id:str,user_id:str,role:str)->WorkspaceMembership:
    if role not in ROLE_SCOPES:raise ValueError('Invalid role')
    m=db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id==workspace_id,WorkspaceMembership.user_id==user_id))
    if m:m.role=role
    else:m=WorkspaceMembership(membership_id=f"mem_{uuid4().hex[:18]}",workspace_id=workspace_id,user_id=user_id,role=role);db.add(m)
    db.commit();db.refresh(m);return m

def issue_session(db:Session,user:UserAccount,workspace_id:str)->tuple[UserSession,str,WorkspaceMembership]:
    m=db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id==workspace_id,WorkspaceMembership.user_id==user.user_id))
    if not m:raise ValueError('User is not a member of this workspace')
    raw='lg_usr_'+secrets.token_urlsafe(32);obj=UserSession(session_id=f"ses_{uuid4().hex[:18]}",user_id=user.user_id,token_hash=hashlib.sha256(raw.encode()).hexdigest(),workspace_id=workspace_id,expires_at=datetime.now(timezone.utc)+timedelta(hours=settings.session_hours));db.add(obj);db.commit();db.refresh(obj);return obj,raw,m

@dataclass
class UserPrincipal:
    user_id:str;email:str;workspace_id:str;role:str;session_id:str
    @property
    def key_id(self):return f"user:{self.user_id}"
    @property
    def scopes(self):return ROLE_SCOPES.get(self.role,set())

def authenticate_session(db:Session,raw_token:str|None,workspace_id:str|None=None,required_scope:str|None=None)->UserPrincipal|None:
    if not raw_token:return None
    if raw_token.lower().startswith('bearer '):raw_token=raw_token[7:].strip()
    if not raw_token.startswith('lg_usr_'):return None
    now=datetime.now(timezone.utc);h=hashlib.sha256(raw_token.encode()).hexdigest();ses=db.scalar(select(UserSession).where(UserSession.token_hash==h,UserSession.revoked_at.is_(None)))
    if not ses or ses.expires_at.replace(tzinfo=ses.expires_at.tzinfo or timezone.utc)<=now:return None
    if workspace_id and ses.workspace_id!=workspace_id:return None
    user=db.get(UserAccount,ses.user_id)
    if not user or user.disabled_at:return None
    m=db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id==ses.workspace_id,WorkspaceMembership.user_id==ses.user_id))
    if not m:return None
    p=UserPrincipal(user.user_id,user.email,ses.workspace_id,m.role,ses.session_id)
    if required_scope and required_scope not in p.scopes:return None
    return p

def current_principal(db:Session,workspace_id:str|None=None,required_scope:str|None=None):return authenticate_session(db,bearer_token_context.get(),workspace_id,required_scope)
def revoke_session(db:Session,principal:UserPrincipal):
    s=db.get(UserSession,principal.session_id)
    if s:s.revoked_at=datetime.now(timezone.utc);db.commit()
