from __future__ import annotations

import base64
import os

import httpx

from .config import settings


def request_rfc3161_timestamp(hex_digest: str) -> dict:
    """Request an RFC 3161 timestamp for a SHA-256 digest.

    The TSA receives only the digest, not the underlying evidence payload. A timestamp
    is accepted only when the response is granted, the SHA-256 message imprint matches,
    and the TSA echoes the request nonce.
    """
    if not settings.tsa_url:
        return {
            "configured": False,
            "external_timestamp": False,
            "provider": "not_configured",
            "note": "Set LOOPGRID_TSA_URL to request RFC 3161 timestamp tokens.",
        }

    try:
        from asn1crypto import algos, tsp
    except Exception:
        return {
            "configured": True,
            "external_timestamp": False,
            "provider": "rfc3161",
            "error": "asn1crypto_not_installed",
        }

    nonce = int.from_bytes(os.urandom(8), "big")
    req = tsp.TimeStampReq(
        {
            "version": "v1",
            "message_imprint": {
                "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
                "hashed_message": bytes.fromhex(hex_digest),
            },
            "nonce": nonce,
            "cert_req": True,
        }
    )

    try:
        response = httpx.post(
            settings.tsa_url,
            content=req.dump(),
            headers={
                "Content-Type": "application/timestamp-query",
                "Accept": "application/timestamp-reply",
            },
            timeout=settings.tsa_timeout_seconds,
        )
        response.raise_for_status()
        raw = response.content

        resp = tsp.TimeStampResp.load(raw)
        status = resp["status"]["status"].native
        if status not in {"granted", "granted_with_mods"}:
            return {
                "configured": True,
                "external_timestamp": False,
                "provider": "rfc3161",
                "status": status,
            }

        token = resp["time_stamp_token"]
        content = token["content"]["encap_content_info"]["content"]
        # asn1crypto already knows tst_info content and returns a parsed TSTInfo here.
        # Calling .native first would turn it into an OrderedDict and break TSTInfo.load().
        info = content.parsed

        imprint = info["message_imprint"]["hashed_message"].native.hex()
        hash_algorithm = info["message_imprint"]["hash_algorithm"]["algorithm"].native
        response_nonce = info["nonce"].native if info["nonce"].native is not None else None
        gen_time = info["gen_time"].native

        imprint_valid = imprint.lower() == hex_digest.lower()
        algorithm_valid = hash_algorithm == "sha256"
        nonce_valid = response_nonce == nonce
        valid = imprint_valid and algorithm_valid and nonce_valid

        return {
            "configured": True,
            "external_timestamp": valid,
            "provider": "rfc3161",
            "status": status,
            "imprint_valid": imprint_valid,
            "hash_algorithm": hash_algorithm,
            "hash_algorithm_valid": algorithm_valid,
            "nonce_valid": nonce_valid,
            "gen_time": gen_time.isoformat() if hasattr(gen_time, "isoformat") else str(gen_time),
            "tsa_url": settings.tsa_url,
            "response_b64": base64.b64encode(raw).decode("ascii"),
            "trust_validation": "imprint_nonce_only",
            "note": (
                "Capture validates the RFC3161 imprint and request nonce. The offline verifier "
                "also validates the token imprint; signer certificate-chain trust can additionally "
                "be checked with --tsa-ca-file and OpenSSL."
            ),
        }
    except Exception as exc:
        return {
            "configured": True,
            "external_timestamp": False,
            "provider": "rfc3161",
            "error": type(exc).__name__,
            "message": str(exc)[:400],
        }
