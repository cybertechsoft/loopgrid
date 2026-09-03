from __future__ import annotations

import hashlib
import os
from unittest.mock import patch

os.environ.setdefault("LOOPGRID_AWS_KMS_KEY_ID", "loopgrid-local-kms-contract-test")
os.environ.setdefault("AWS_REGION", "ap-south-1")

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from app.signing import AwsKmsEcdsaSigner


class FakeKmsClient:
    def __init__(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.last_sign_request = None

    def get_public_key(self, KeyId):
        public_key = self.private_key.public_key()
        der = public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return {"PublicKey": der}

    def sign(self, **kwargs):
        self.last_sign_request = kwargs
        signature = self.private_key.sign(
            kwargs["Message"],
            ec.ECDSA(utils.Prehashed(hashes.SHA256())),
        )
        return {"Signature": signature}


def main() -> None:
    fake = FakeKmsClient()
    with patch("boto3.client", return_value=fake):
        signer = AwsKmsEcdsaSigner()
        digest = hashlib.sha256(b"LoopGrid AWS KMS contract validation").hexdigest()
        signature = signer.sign_hash(digest)
        assert signer.verify_hash(digest, signature)
        tampered = hashlib.sha256(b"LoopGrid AWS KMS contract validation TAMPERED").hexdigest()
        assert not signer.verify_hash(tampered, signature)
        request = fake.last_sign_request
        assert request["KeyId"] == "loopgrid-local-kms-contract-test"
        assert request["MessageType"] == "DIGEST"
        assert request["SigningAlgorithm"] == "ECDSA_SHA_256"
        assert request["Message"] == bytes.fromhex(digest)

    print("[PASS] P-256 public key accepted")
    print("[PASS] SHA-256 digest supplied to signer")
    print("[PASS] MessageType = DIGEST")
    print("[PASS] SigningAlgorithm = ECDSA_SHA_256")
    print("[PASS] ECDSA signature verified locally")
    print("[PASS] Tampered digest rejected")
    print("[PASS] AWS KMS signer contract compatible")
    print("\nKMS CONTRACT RESULT: PASS")


if __name__ == "__main__":
    main()
