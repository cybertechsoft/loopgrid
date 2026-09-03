#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

import httpx


def log(step: str, ok: bool = True, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {step}{' - ' + detail if detail else ''}")
    if not ok:
        raise RuntimeError(f"{step}: {detail}")


def info(step: str, detail: str = "") -> None:
    print(f"[INFO] {step}{' - ' + detail if detail else ''}")


class LG:
    def __init__(self, base: str, admin_key: str | None = None):
        self.base = base.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
        self.admin_key = admin_key

    def req(self, method: str, path: str, *, key: str | None = None, **kw):
        headers = kw.pop("headers", {}).copy()
        use = key if key is not None else self.admin_key
        if use:
            headers["X-LoopGrid-Key"] = use
        r = self.client.request(method, self.base + path, headers=headers, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:700]}")
        return r


def live_openai(prompt: str):
    key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("LOOPGRID_TEST_OPENAI_MODEL")
    if not key or not model:
        return None
    t = time.perf_counter()
    r = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "input": prompt},
        timeout=60,
    )
    r.raise_for_status()
    j = r.json()
    text = j.get("output_text") or ""
    if not text:
        parts = []
        for item in j.get("output", []):
            for c in item.get("content", []) if isinstance(item, dict) else []:
                if isinstance(c, dict) and c.get("text"):
                    parts.append(c["text"])
        text = "\n".join(parts)
    return {
        "provider": "openai",
        "model": model,
        "response": text,
        "provider_request_id": j.get("id"),
        "usage": j.get("usage"),
        "latency_ms": round((time.perf_counter() - t) * 1000, 1),
    }


def live_anthropic(prompt: str):
    key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("LOOPGRID_TEST_ANTHROPIC_MODEL")
    if not key or not model:
        return None
    t = time.perf_counter()
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    r.raise_for_status()
    j = r.json()
    text = "\n".join(
        x.get("text", "")
        for x in j.get("content", [])
        if isinstance(x, dict) and x.get("type") == "text"
    )
    return {
        "provider": "anthropic",
        "model": model,
        "response": text,
        "provider_request_id": j.get("id"),
        "usage": j.get("usage"),
        "latency_ms": round((time.perf_counter() - t) * 1000, 1),
    }


def choose_review_scenario(active_policy: dict) -> tuple[float, float, dict]:
    """Choose an amount/authority pair that deterministically exercises human review.

    This intentionally adapts to the currently active amount-threshold policy so the
    validation runner is not coupled to demo policy v17.3 or a fixed $720 threshold.
    """
    rule = active_policy.get("rule") or {}
    if rule.get("type") != "amount_threshold":
        raise RuntimeError(
            f"Active policy {active_policy.get('policy_id')}:{active_policy.get('version')} "
            "is not an amount_threshold policy; the real-scenario runner cannot derive "
            "a deterministic human-review amount from it."
        )
    auto = float(rule.get("auto_approve_max", 0) or 0)
    hard = float(rule.get("hard_limit", 0) or 0)
    if hard and hard <= auto:
        raise RuntimeError(
            f"Active policy has no human-review band (auto_approve_max={auto}, hard_limit={hard})."
        )

    if hard:
        amount = auto + max(1.0, (hard - auto) / 2.0)
        amount = min(amount, hard)
        authority_limit = hard
    else:
        step = max(1.0, auto * 0.25 if auto else 100.0)
        amount = auto + step
        authority_limit = amount + step

    # Prefer clean currency values for human-readable test output.
    amount = round(amount, 2)
    authority_limit = round(max(authority_limit, amount), 2)
    return amount, authority_limit, rule


def main() -> None:
    ap = argparse.ArgumentParser(
        description="External HTTP real-scenario validation for LoopGrid v0.8 Design Partner Release (state-safe runner)"
    )
    ap.add_argument(
        "--base-url", default=os.getenv("LOOPGRID_BASE_URL", "http://127.0.0.1:8000")
    )
    ap.add_argument("--admin-key", default=os.getenv("LOOPGRID_ADMIN_KEY"))
    ap.add_argument("--provider", choices=["none", "openai", "anthropic"], default="none")
    ap.add_argument("--output-dir", default="real-test-output")
    ap.add_argument("--workspace-id", default="default")
    args = ap.parse_args()

    workspace_id = args.workspace_id
    run_id = uuid.uuid4().hex[:12]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    lg = LG(args.base_url, args.admin_key)

    health = lg.req("GET", "/health").json()
    log("Server health", health.get("ok") is True, health.get("version", ""))
    ready = lg.req("GET", "/ready").json()
    log("Server readiness", ready.get("ready") is True, json.dumps(ready))
    posture = lg.req("GET", "/api/v1/system/info").json()
    log(
        "Trust posture endpoint",
        True,
        f"signer={posture['signer']['provider']} vault={posture['payload_vault']['algorithm']}",
    )
    pr = lg.req("GET", "/api/v1/pilot/readiness").json()
    log(
        "Controlled pilot readiness",
        pr.get("controlled_pilot_ready") is True,
        pr.get("overall", ""),
    )

    issued = lg.req(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/keys",
        json={"name": f"v0.8 design partner real scenario {run_id}", "scopes": ["ingest", "read", "review"]},
    ).json()
    key = issued["api_key"]
    log("Scoped service API key issued", key.startswith("lg_"), issued["key_id"])

    # Discover the current active policy before constructing the transaction. This is the
    # key state-isolation fix: prior UI policy experiments no longer make the runner fail.
    policies = lg.req(
        "GET", f"/api/v1/workspaces/{workspace_id}/policies", key=key
    ).json()
    active = next(
        (
            p
            for p in policies
            if p.get("policy_id") == "refund-policy" and p.get("active") is True
        ),
        None,
    )
    if not active:
        raise RuntimeError("No active refund-policy found in the target workspace")

    amount, authority_limit, rule = choose_review_scenario(active)
    info(
        "Active policy discovered",
        f"refund-policy v{active.get('version')} auto<={rule.get('auto_approve_max')} "
        f"hard<={rule.get('hard_limit')} - validation amount=${amount:g}",
    )

    amount_text = f"${amount:,.2f}".rstrip("0").rstrip(".")
    original = f"I was charged twice. Please refund the duplicate {amount_text} charge."
    idem_prefix = f"real-scenario:{run_id}"
    body = {
        "workspace_id": workspace_id,
        "privacy_mode": "full",
        "idempotency_key": f"{idem_prefix}:decision",
        "decision_type": "customer_refund",
        "service_name": "real-support-agent",
        "agent": {"id": "real-support-agent", "version": "pilot-1"},
        "authority": {
            "acting_for": "Acme Support",
            "scope": ["refund:create"],
            "limit_usd": authority_limit,
        },
        "model": {
            "provider": args.provider if args.provider != "none" else "local-test",
            "name": os.getenv("LOOPGRID_TEST_OPENAI_MODEL")
            or os.getenv("LOOPGRID_TEST_ANTHROPIC_MODEL")
            or "deterministic-test-agent",
        },
        "context": {
            "prompt_version": "support-real-v1",
            "retrieval_refs": [f"refund-policy-{active.get('version')}"],
        },
        "input": {"message": original, "customer_ref": f"cust_real_test_{run_id}"},
        "proposed_action": {
            "tool": "stripe.refunds.create",
            "amount": amount,
            "currency": "USD",
        },
        "metadata": {
            "capture_source": "real_scenario_test.py",
            "validation_run_id": run_id,
        },
    }

    d = lg.req("POST", "/api/v1/decisions", key=key, json=body).json()
    did = d["decision_id"]
    log("Decision captured through public API", True, did)
    idem = lg.req("POST", "/api/v1/decisions", key=key, json=body).json()
    log(
        "Idempotent retry",
        idem.get("idempotent_replay") is True and idem["decision_id"] == did,
    )

    pp = (
        live_openai(original)
        if args.provider == "openai"
        else live_anthropic(original)
        if args.provider == "anthropic"
        else None
    )
    if args.provider != "none":
        log(
            f"Live {args.provider} call",
            pp is not None,
            "provider API + test model configured",
        )
    if pp is None:
        pp = {
            "provider": "local-test",
            "model": "deterministic-test-agent",
            "response": f"Duplicate charge detected. Proposed refund: {amount_text}.",
            "latency_ms": 12.4,
        }
    lg.req(
        "POST",
        f"/api/v1/decisions/{did}/events",
        key=key,
        json={
            "event_type": "model_completed",
            "actor_type": "agent",
            "actor_id": "real-support-agent",
            "idempotency_key": f"{idem_prefix}:model-complete",
            "payload": pp,
        },
    )
    log("Model evidence appended")

    pe = lg.req(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/policies/evaluate",
        key=key,
        json={
            "policy_id": "refund-policy",
            "proposed_action": {"amount": amount, "currency": "USD"},
            "authority": {"limit_usd": authority_limit},
        },
    ).json()
    log(
        "Deterministic policy evaluated",
        pe.get("decision") == "human_approval_required",
        json.dumps(pe),
    )
    lg.req(
        "POST",
        f"/api/v1/decisions/{did}/events",
        key=key,
        json={
            "event_type": "policy_evaluated",
            "actor_type": "policy",
            "actor_id": f"refund-policy-{pe.get('version')}",
            "idempotency_key": f"{idem_prefix}:policy",
            "payload": pe,
        },
    )

    pending = lg.req(
        "GET", f"/api/v1/reviews?workspace_id={workspace_id}", key=key
    ).json()
    log("Decision entered human review queue", any(x["decision_id"] == did for x in pending))
    rv = lg.req(
        "POST",
        f"/api/v1/decisions/{did}/review",
        key=key,
        json={
            "action": "approve",
            "reviewer": "pilot-reviewer@acme.test",
            "reason": "Duplicate charge verified in source system",
        },
    ).json()
    log("Human approval recorded", rv.get("state") == "approve")

    cents = int(round(amount * 100))
    ext_ref = f"re_real_scenario_{run_id}"
    lg.req(
        "POST",
        f"/api/v1/decisions/{did}/events",
        key=key,
        json={
            "event_type": "tool_executed",
            "actor_type": "tool",
            "actor_id": "stripe-test-double",
            "idempotency_key": f"{idem_prefix}:tool",
            "payload": {
                "tool": "stripe.refunds.create",
                "request": {"amount": cents, "currency": "usd"},
                "external_reference": ext_ref,
                "environment": "test",
            },
        },
    )
    lg.req(
        "POST",
        f"/api/v1/decisions/{did}/events",
        key=key,
        json={
            "event_type": "outcome_observed",
            "actor_type": "system",
            "actor_id": "outcome-verifier",
            "idempotency_key": f"{idem_prefix}:outcome",
            "payload": {
                "status": "succeeded",
                "verified_against": "stripe-test-double",
                "external_reference": ext_ref,
                "amount": amount,
            },
        },
    )
    log("Action and observed outcome appended")

    detail = lg.req("GET", f"/api/v1/decisions/{did}", key=key).json()
    cov = detail["coverage"]
    log(
        "Evidence lifecycle complete",
        cov.get("complete") is True and cov.get("score") == 100,
        f"{cov.get('label')} {cov.get('score')}%",
    )
    integ = lg.req(
        "GET", f"/api/v1/integrity/verify?workspace_id={workspace_id}", key=key
    ).json()
    log(
        "Workspace cryptographic verification",
        integ.get("valid") is True,
        f"events={integ.get('checked_events')}",
    )
    tamper = lg.req(
        "POST", f"/api/v1/decisions/{did}/tamper-test", key=key, json={}
    ).json()
    log(
        "Tamper detection",
        tamper.get("simulated_tamper", {}).get("detected") is True
        and tamper.get("production_record_unchanged") is True,
    )

    cp = lg.req(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/checkpoint",
        key=args.admin_key,
        json={},
    ).json() if args.admin_key else lg.req(
        "POST", f"/api/v1/workspaces/{workspace_id}/checkpoint", json={}
    ).json()
    tsa_configured = bool((posture.get("timestamping") or {}).get("tsa_url_configured"))
    checkpoint_ok = bool(cp.get("signature")) and (
        not tsa_configured or cp.get("external_timestamp") is True
    )
    log(
        "Signed workspace checkpoint",
        checkpoint_ok,
        f"external_timestamp={cp.get('external_timestamp')}",
    )
    decision_head = detail["events"][-1]["proof"]["chain_hash"]
    log(
        "Checkpoint binds target decision head",
        cp.get("chain_hash") == decision_head,
        f"ledger_seq={cp.get('ledger_seq')}",
    )

    z = out / f"{did}-evidence.zip"
    z.write_bytes(lg.req("GET", f"/api/v1/decisions/{did}/evidence", key=key).content)
    if cp.get("external_timestamp"):
        with zipfile.ZipFile(z) as zz:
            tsr_present = "timestamp.tsr" in zz.namelist()
            tsr_bytes = len(zz.read("timestamp.tsr")) if tsr_present else 0
        log(
            "RFC3161 token included in evidence bundle",
            tsr_present and tsr_bytes > 0,
            f"bytes={tsr_bytes}",
        )

    verifier = Path(__file__).resolve().parents[1] / "verifier" / "loopgrid_verify.py"
    if not verifier.exists():
        # When this hotfix file is downloaded separately, allow it to live in scripts/ or
        # the repository root while still resolving the bundled verifier.
        alt = Path.cwd() / "verifier" / "loopgrid_verify.py"
        verifier = alt if alt.exists() else verifier
    verifier_env = os.environ.copy()
    # Force deterministic UTF-8 subprocess I/O on Windows. The verifier itself uses
    # ASCII status markers, but this also protects future structured output/details.
    verifier_env.setdefault("PYTHONUTF8", "1")
    verifier_python = os.getenv("LOOPGRID_VERIFIER_PYTHON") or sys.executable
    proc = subprocess.run(
        [
            verifier_python,
            str(verifier),
            str(z),
            "--expected-key-id",
            posture["signer"]["key_id"],
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=verifier_env,
    )
    if proc.returncode == 0:
        verifier_detail = "standalone verifier exited 0 and signer pin matched"
    else:
        stdout_tail = (proc.stdout or "").strip()[-900:]
        stderr_tail = (proc.stderr or "").strip()[-900:]
        verifier_detail = (
            f"exit={proc.returncode}; stdout={stdout_tail!r}; stderr={stderr_tail!r}"
        )
    log(
        "Offline evidence verification",
        proc.returncode == 0,
        verifier_detail,
    )

    wz = out / f"{did}-withheld.zip"
    wz.write_bytes(
        lg.req(
            "GET", f"/api/v1/decisions/{did}/evidence?include_payloads=false", key=key
        ).content
    )
    with zipfile.ZipFile(wz) as zz:
        combined = b"\n".join(
            zz.read(n)
            for n in zz.namelist()
            if n.endswith((".json", ".jsonl", ".html", ".txt"))
        )
    log(
        "Disclosure-withheld export",
        original.encode() not in combined,
        "raw customer text absent",
    )

    otlp = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "real-agent-service"}}
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "real-scenario"},
                        "spans": [
                            {
                                "traceId": f"realtrace{run_id}",
                                "spanId": f"span{run_id}"[:16],
                                "name": "chat",
                                "attributes": [
                                    {
                                        "key": "gen_ai.provider.name",
                                        "value": {"stringValue": "test-provider"},
                                    },
                                    {
                                        "key": "gen_ai.request.model",
                                        "value": {"stringValue": "test-model"},
                                    },
                                    {
                                        "key": "loopgrid.decision.type",
                                        "value": {"stringValue": "real_otlp_capture"},
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    otr = lg.req(
        "POST",
        "/v1/traces",
        key=key,
        headers={"X-LoopGrid-Workspace": workspace_id},
        json=otlp,
    ).json()
    log("OTLP/HTTP JSON ingestion", otr.get("loopgrid", {}).get("accepted") == 1)

    result = {
        "validation_run_id": run_id,
        "workspace_id": workspace_id,
        "active_policy": active,
        "selected_amount": amount,
        "authority_limit": authority_limit,
        "decision_id": did,
        "evidence_zip": str(z),
        "withheld_zip": str(wz),
        "provider": args.provider,
        "integrity": integ,
        "coverage": cov,
        "pilot_readiness": pr,
        "checkpoint": cp,
    }
    (out / "real-scenario-result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print("\nREAL SCENARIO RESULT: PASS")
    print(
        f"Policy: refund-policy v{active.get('version')}\n"
        f"Validation amount: {amount_text}\n"
        f"Decision: {did}\nEvidence: {z}\nResult: {out / 'real-scenario-result.json'}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nREAL SCENARIO RESULT: FAIL - {e}", file=sys.stderr)
        sys.exit(1)
