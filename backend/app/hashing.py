"""
LoopGrid Hash Chain
===================

Cryptographic immutability for the decision ledger.
Each decision's hash includes the previous decision's hash,
creating a tamper-evident chain. If any record is modified 
or deleted, the chain breaks and verification detects it.
"""

import hashlib
import json
from typing import Optional


def compute_content_hash(decision_data: dict) -> str:
    """
    Compute SHA-256 hash of a decision's content.
    Deterministic: same content always produces same hash.
    """
    hashable = {
        "service_name": decision_data.get("service_name"),
        "decision_type": decision_data.get("decision_type"),
        "input": decision_data.get("input"),
        "model": decision_data.get("model"),
        "output": decision_data.get("output"),
        "prompt": decision_data.get("prompt"),
        "tool_calls": decision_data.get("tool_calls"),
        "metadata": decision_data.get("metadata"),
    }
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_chain_hash(content_hash: str, previous_chain_hash: Optional[str] = None) -> str:
    """
    Compute chain hash linking this decision to the previous one.
    chain_hash = SHA-256(content_hash + previous_chain_hash)
    If no previous decision, previous_chain_hash is "GENESIS".
    """
    prev = previous_chain_hash or "GENESIS"
    payload = f"{content_hash}:{prev}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(decisions: list) -> dict:
    """
    Verify integrity of decisions (ordered by created_at ASC).
    Returns dict with valid, total, broken_at, message.
    """
    if not decisions:
        return {"valid": True, "total": 0, "broken_at": None, "message": "No decisions to verify"}

    previous_chain_hash = None

    for i, decision in enumerate(decisions):
        decision_data = {
            "service_name": decision.service_name,
            "decision_type": decision.decision_type,
            "input": decision.input,
            "model": decision.model,
            "output": decision.output,
            "prompt": decision.prompt,
            "tool_calls": decision.tool_calls,
            "metadata": decision.meta,
        }

        expected_content_hash = compute_content_hash(decision_data)

        if decision.content_hash != expected_content_hash:
            return {
                "valid": False, "total": i + 1, "broken_at": decision.id,
                "message": f"Content hash mismatch at decision {decision.id} — data was modified"
            }

        expected_chain_hash = compute_chain_hash(expected_content_hash, previous_chain_hash)

        if decision.chain_hash != expected_chain_hash:
            return {
                "valid": False, "total": i + 1, "broken_at": decision.id,
                "message": f"Chain hash mismatch at decision {decision.id} — chain was broken"
            }

        previous_chain_hash = decision.chain_hash

    return {
        "valid": True, "total": len(decisions), "broken_at": None,
        "message": f"All {len(decisions)} decisions verified — ledger integrity confirmed"
    }
