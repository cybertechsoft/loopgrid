from __future__ import annotations
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from .config import settings
from .crypto import sha256_hex

class Signer(Protocol):
    provider:str
    algorithm:str
    key_id:str
    def sign_hash(self, hex_hash:str)->str: ...
    def verify_hash(self, hex_hash:str, signature_b64:str)->bool: ...
    def public_key_pem(self)->bytes: ...
    def posture(self)->dict: ...


def _parent(path:Path): path.parent.mkdir(parents=True,exist_ok=True)

class LocalEd25519Signer:
    provider="local_ed25519";algorithm="Ed25519"
    def __init__(self):
        priv_path=settings.signing_key_path;pub_path=settings.public_key_path;_parent(priv_path);_parent(pub_path)
        if priv_path.exists():
            private=serialization.load_pem_private_key(priv_path.read_bytes(),password=None)
            if not isinstance(private,Ed25519PrivateKey):raise RuntimeError("Configured local signing key is not Ed25519")
        else:
            private=Ed25519PrivateKey.generate();priv_path.write_bytes(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        self.private=private;self.public=private.public_key();pem=self.public.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        if not pub_path.exists() or pub_path.read_bytes()!=pem:pub_path.write_bytes(pem)
        raw=self.public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);self.key_id="ed25519:"+sha256_hex(raw)[:16]
    def sign_hash(self,hex_hash):return base64.b64encode(self.private.sign(bytes.fromhex(hex_hash))).decode("ascii")
    def verify_hash(self,hex_hash,signature_b64):
        try:self.public.verify(base64.b64decode(signature_b64),bytes.fromhex(hex_hash));return True
        except Exception:return False
    def public_key_pem(self):return self.public.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    def posture(self):return {"provider":self.provider,"algorithm":self.algorithm,"key_id":self.key_id,"hardware_backed":False,"production_recommendation":"Use AWS KMS for a hardware-backed production signing boundary."}

class AwsKmsEcdsaSigner:
    provider="aws_kms";algorithm="ECDSA_SHA_256"
    def __init__(self):
        if not settings.aws_kms_key_id:raise RuntimeError("LOOPGRID_AWS_KMS_KEY_ID is required for aws_kms signer")
        try:import boto3
        except Exception as e:raise RuntimeError("boto3 is required for AWS KMS signing") from e
        self.client=boto3.client("kms",region_name=settings.aws_region);self.kms_key_id=settings.aws_kms_key_id
        resp=self.client.get_public_key(KeyId=self.kms_key_id);self.public=serialization.load_der_public_key(resp["PublicKey"])
        if not isinstance(self.public,ec.EllipticCurvePublicKey):raise RuntimeError("AWS KMS key must be an asymmetric EC signing key")
        pem=self.public.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo);self._pem=pem
        self.key_id="aws-kms:"+sha256_hex(pem)[:16]
    def sign_hash(self,hex_hash):
        r=self.client.sign(KeyId=self.kms_key_id,Message=bytes.fromhex(hex_hash),MessageType="DIGEST",SigningAlgorithm="ECDSA_SHA_256")
        return base64.b64encode(r["Signature"]).decode("ascii")
    def verify_hash(self,hex_hash,signature_b64):
        try:self.public.verify(base64.b64decode(signature_b64),bytes.fromhex(hex_hash),ec.ECDSA(utils.Prehashed(hashes.SHA256())));return True
        except Exception:return False
    def public_key_pem(self):return self._pem
    def posture(self):return {"provider":self.provider,"algorithm":self.algorithm,"key_id":self.key_id,"hardware_backed":True,"kms_key_id":self.kms_key_id}


def load_signer()->Signer:
    name=(settings.signer_provider or "local_ed25519").lower()
    if name=="aws_kms":return AwsKmsEcdsaSigner()
    if name!="local_ed25519":raise RuntimeError(f"Unsupported signer provider: {name}")
    return LocalEd25519Signer()

signer=load_signer()
