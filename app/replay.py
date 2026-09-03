from __future__ import annotations
import os
import httpx


def policy_replay(summary: dict, threshold: float | None) -> dict:
    action = summary.get("proposed_action") or {}
    amount = float(action.get("amount", 0) or 0)
    original_policy = summary.get("policy") or {}
    if threshold is None:
        threshold = float(original_policy.get("human_approval_threshold", 500))
    result = "human_approval_required" if amount > threshold else "auto_allowed"
    original_decision = original_policy.get("decision") or "unknown"
    return {
        "mode": "policy",
        "original": {
            "threshold": original_policy.get("human_approval_threshold"),
            "amount": amount,
            "decision": original_decision,
            "policy_version": original_policy.get("version"),
        },
        "counterfactual": {
            "threshold": threshold,
            "amount": amount,
            "decision": result,
            "policy_version": "counterfactual",
        },
        "changed": result != original_decision,
        "explanation": (
            f"The ${amount:,.0f} action would be {'escalated for human approval' if result == 'human_approval_required' else 'allowed automatically'} "
            f"under a ${threshold:,.0f} approval threshold."
        ),
        "note": "Policy replay is deterministic and appends an analysis event without altering the original production events.",
    }


async def live_replay(summary: dict, provider: str | None, model: str | None, prompt: str | None) -> dict:
    provider = provider or "openai"
    message = (summary.get("input") or {}).get("message") or str(summary.get("input") or {})
    prompt = prompt or "You are reviewing a historical AI decision. Return a concise recommended action and reasoning."

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return {"mode": "live", "status": "unavailable", "reason": "OPENAI_API_KEY is not configured"}
        payload = {"model": model or "gpt-4.1-mini", "input": [{"role": "system", "content": prompt}, {"role": "user", "content": message}]}
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {key}"}, json=payload)
            r.raise_for_status()
            data = r.json()
        return {"mode": "live", "status": "ok", "provider": "openai", "raw": data}

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return {"mode": "live", "status": "unavailable", "reason": "ANTHROPIC_API_KEY is not configured"}
    payload = {"model": model or "claude-sonnet-4-20250514", "max_tokens": 500, "system": prompt, "messages": [{"role": "user", "content": message}]}
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=payload)
        r.raise_for_status()
        data = r.json()
    return {"mode": "live", "status": "ok", "provider": "anthropic", "raw": data}
