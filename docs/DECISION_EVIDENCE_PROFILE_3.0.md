# LoopGrid Decision Evidence Profile 3.0-draft

Status: **draft / external-integration readiness**

This document defines the v0.8 canonical evidence envelope and lifecycle. It is a LoopGrid application profile, not a formal standards-body specification.

## 1. Purpose

A consequential agent decision should be reconstructable as evidence independent of the agent runtime, model provider, workflow engine or observability platform that produced it.

The profile captures seven questions:

1. **Who/what acted?** — agent and service identity.
2. **On whose authority?** — delegated scope, acting-for identity and relevant limits.
3. **What model/context was involved?** — provider/model/config and prompt/retrieval/context references or commitments.
4. **Which rule allowed/blocked/escalated it?** — policy ID, version, rule digest, input commitment and result.
5. **What human oversight occurred?** — reviewer identity, decision and reason as a separate signed event.
6. **What action actually executed?** — external tool/operation and external request/reference.
7. **What happened afterward?** — observed external outcome plus cryptographic evidence history.

## 2. Decision envelope

`decision_created` contains the production-time envelope:

```json
{
  "spec_version": "loopgrid/3.0-draft",
  "decision_type": "customer_refund",
  "service_name": "support-agent",
  "agent": {
    "id": "support-agent-04",
    "version": "1.8.3",
    "deployment_sha": "..."
  },
  "authority": {
    "acting_for": "Acme Support",
    "scope": ["refund:create"],
    "limit_usd": 1500
  },
  "model": {
    "provider": "openai",
    "name": "..."
  },
  "context": {
    "prompt_version": "support-v14",
    "retrieval_refs": ["refund-policy-v17.3"]
  },
  "input": {},
  "proposed_action": {
    "tool": "stripe.refunds.create",
    "amount": 720,
    "currency": "USD"
  },
  "metadata": {}
}
```

Privacy modes may replace some/all payload fields with commitments; the signed event body records the privacy mode and payload commitment.

## 3. Canonical event types

Primary production lifecycle:

```text
decision_created
model_completed
policy_evaluated
human_approved | human_rejected        # only when policy requires review
tool_requested                         # optional request evidence
tool_executed | tool_result | mcp_tool_result
outcome_observed
```

Append-only follow-on evidence may include:

```text
human_adjudicated
incident_flagged
replay_executed
checkpoint_created
telemetry_ingested
mcp_tool_requested
payload_erased
```

A correction/adjudication never rewrites the original production event.

## 4. Policy provenance

Policy definitions have a deterministic digest over:

```json
{
  "workspace_id": "...",
  "policy_id": "...",
  "version": "...",
  "rule": {}
}
```

`policy_evaluated` records:

```text
policy_id
version
policy_digest
input_commitment
decision
reason
rule / relevant thresholds
```

`input_commitment` commits to:

```json
{
  "proposed_action": {},
  "authority": {},
  "context": {}
}
```

This separates the stable policy identity from the specific evaluation inputs.

## 5. Lifecycle projection

The ledger is the source of truth; lifecycle state is a deterministic projection.

Representative states:

```text
captured
model_captured
policy_evaluated
awaiting_human_review
authorized_awaiting_execution
approved_awaiting_execution
awaiting_outcome
blocked
rejected
evidence_complete
```

The server rejects consequential transitions that contradict already-recorded policy/review evidence.

## 6. Cryptographic event body

Each event signs a content/chain commitment derived from:

```text
event_id
decision_id
workspace_id
event_type
occurred_at
actor
privacy_mode
payload_commitment
signed payload projection
```

A SHA-256 content hash is chained to the previous same-workspace chain hash. The resulting chain hash is signed with the configured signer.

The profile is **tamper-evident**. The local-file signer alone is not an independent hardware trust boundary.

## 7. Evidence Bundle v2

The portable bundle separates signed evidence, continuity witnesses, signer identity, policy/lifecycle projections and optional disclosures. The verifier must recompute event hashes, verify chain continuity/signatures, verify disclosure commitments and optionally pin signer identity out of band.

## 8. Reconstruction vs replay

**Forensic reconstruction** describes what was actually recorded at production time.

**Counterfactual replay** evaluates the historic case under a different model/prompt/policy and appends a replay event. Replay never rewrites production evidence and does not claim deterministic reproduction of hosted LLM behavior.

## 9. Compliance language

This profile can support record-keeping, oversight, risk, audit and regulatory evidence workflows. Evidence integrity by itself is not a legal compliance determination.
