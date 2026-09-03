from __future__ import annotations
import hashlib,json

def canonical_json(obj) -> bytes:
    # Deterministic canonical JSON profile used by evidence_profile=3.0-draft.
    # Floats/NaN are deliberately rejected by allow_nan=False. Formal RFC8785 conformance
    # remains a future standards-hardening step and is not claimed by this release.
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")

def sha256_hex(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def public_key_pem(public)->bytes:
    from cryptography.hazmat.primitives import serialization
    return public.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)

def verify_hash(public,hex_hash:str,signature_b64:str)->bool:
    import base64
    try:public.verify(base64.b64decode(signature_b64),bytes.fromhex(hex_hash));return True
    except Exception:return False
