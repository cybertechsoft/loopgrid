from __future__ import annotations
from typing import Any
from .crypto import canonical_json,sha256_hex
SENSITIVE_HINTS={"email","phone","name","address","message","prompt","response","customer","account","token","secret","password","ssn","dob","content","body"}
def _is_sensitive(key,path,custom):
    k=key.lower().replace("-","_");p=path.lower().replace("-","_");return any(h in k for h in SENSITIVE_HINTS) or k in custom or p in custom
def _commit(value):return {"redacted":True,"sha256":sha256_hex(canonical_json(value)),"type":type(value).__name__}
def redact_payload(value,*,custom_fields=None,path=""):
    custom_fields=custom_fields or set()
    if isinstance(value,dict):
        out={}
        for k,v in value.items():
            p=f"{path}.{k}" if path else k;out[k]=_commit(v) if _is_sensitive(k,p,custom_fields) else redact_payload(v,custom_fields=custom_fields,path=p)
        return out
    if isinstance(value,list):return [redact_payload(v,custom_fields=custom_fields,path=f"{path}[]") for v in value]
    return value
def apply_privacy(payload,mode,custom_fields=None):
    if mode=="full":return payload,None
    commitment=sha256_hex(canonical_json(payload))
    if mode=="proof_only":return {"proof_only":True,"payload_sha256":commitment},commitment
    return redact_payload(payload,custom_fields=set(custom_fields or [])),commitment
