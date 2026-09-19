# LoopGrid v0.8 — Design Partner Release

**The evidence plane for AI agents.**

LoopGrid captures and seals the evidence around consequential AI/agent decisions: **agent identity, delegated authority, model/context, policy, human oversight, tool/action, observed outcome and cryptographic proof**. The result is a signed, tamper-evident record that can be exported and verified independently.

> **Release posture:** approved for controlled design-partner technical evaluation. **Not Production GA.** Evidence integrity can support governance, audit and dispute workflows; it is not by itself a legal compliance determination.

## Why LoopGrid

Agent runtimes execute. Observability explains. Control planes govern. **LoopGrid proves what happened.**

A consequential decision should answer:

- Which agent/version acted?
- What authority was delegated?
- Which model/context informed the decision?
- Which policy/version applied and what did it decide?
- Was human oversight required and what happened?
- Which external tool/action actually executed?
- What outcome was observed?
- Can an independent party verify the record later?

## Evidence lifecycle

```text
CAPTURE → SEAL → VERIFY → INVESTIGATE → REVIEW → REPLAY → PROVE
```

The append-only decision lifecycle includes `decision_created`, `model_completed`, `policy_evaluated`, human review events, tool/action evidence, `outcome_observed` and optional later replay/adjudication events. LoopGrid derives the current state from that history and rejects impossible consequential-event ordering.

## v0.8.1 interoperability update

- `/v1/traces` now accepts standard OTLP/HTTP binary protobuf and JSON trace payloads.
- `Content-Encoding: gzip` is supported for OTLP/HTTP trace requests.
- OTLP success responses now use the standard `ExportTraceServiceResponse` encoding and match the request `Content-Type`.
- Decoded OTLP request bodies are bounded by `LOOPGRID_MAX_REQUEST_BODY_BYTES` to limit decompression expansion.
- Existing evidence, signing, bundle and verifier formats are unchanged from v0.8.0.

## v0.8 highlights

- PostgreSQL-backed Docker deployment path.
- Production-mode safety guard for auth, secrets, PostgreSQL and CORS.
- Workspace-scoped API keys and human RBAC.
- SHA-256 workspace hash chains + persistent local Ed25519 signing.
- Signed workspace checkpoints.
- Portable Evidence Bundle v2 / Evidence Profile `3.0-draft`.
- Signer-pinned standalone verifier.
- FULL / REDACTED / PROOF-ONLY privacy modes.
- AES-256-GCM disclosure vault with erasable payloads.
- Deterministic policy provenance and human-review evidence.
- REST, Python, TypeScript/JavaScript, OpenTelemetry/OTLP (HTTP protobuf + JSON) and MCP paths.
- Optional live OpenAI/Anthropic replay/provider validation helpers.
- Optional RFC3161 timestamp and AWS KMS adapter paths.

## Fast local evaluation

For a no-Docker, no-account evaluation path, install the repository dependencies once and run the cross-platform quickstart:

```bash
python -m pip install -r requirements.txt
python scripts/quickstart.py
```

The quickstart uses an isolated temporary SQLite database and temporary local Ed25519 signer. It creates a synthetic refund decision with policy evaluation, human approval, tool execution and observed outcome, exports a portable evidence bundle, and verifies that bundle with an out-of-band trusted public key. It does not modify an existing LoopGrid database or deployment.

Expected final output:

```text
[OK] Decision captured: dec_...
[OK] Evidence exported: .../demo-output/evidence.zip
[OK] Evidence coverage: 100%
[OK] VERIFIED
```

Artifacts are written to `demo-output/` and are synthetic evaluation data only.

## Container image

The repository publishes a multi-platform development image from `main` to GitHub Container Registry:

```bash
docker pull ghcr.io/cybertechsoft/loopgrid:edge
docker run --rm -p 8000:8000 -v loopgrid_demo_data:/app/data ghcr.io/cybertechsoft/loopgrid:edge
```

Then open `http://127.0.0.1:8000/`. The `edge` tag tracks tested `main`; versioned and `latest` container tags are published from future GitHub releases. The default container invocation above is for local evaluation, not the production design-partner posture described below.

## Quickest design-partner deployment

Requires Docker Desktop/Engine and Python 3.10+.

```powershell
python scripts\generate_pilot_env.py
powershell -ExecutionPolicy Bypass -File .\validate_pilot.ps1
```

The first command generates strong local secrets into `.env` without printing them. The second starts PostgreSQL + LoopGrid and runs the deployment validation gate.

Do **not** run `docker compose down -v` unless you intentionally want to destroy local pilot data.

## Local development

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python run.py
```

Open:

- UI: `http://127.0.0.1:8000/`
- OpenAPI: `http://127.0.0.1:8000/docs`
- readiness: `http://127.0.0.1:8000/ready`
- trust posture: `http://127.0.0.1:8000/api/v1/system/info`

## Python SDK

```bash
pip install loopgrid
```

```python
from loopgrid import LoopGrid

lg = LoopGrid(base_url="http://localhost:8000", api_key="lg_live_...")

d = lg.record_decision(
    decision_type="customer_refund",
    agent={"id": "support-agent", "version": "1.0"},
    authority={"acting_for": "Acme", "limit_usd": 1500, "scope": ["refund:create"]},
    model={"provider": "openai", "name": "gpt-5"},
    context={"prompt_version": "support-v1"},
    proposed_action={"tool": "stripe.refunds.create", "amount": 1000, "currency": "USD"},
)

print(d["decision_id"])
```

See `examples/refund_human_review.py` for the complete policy → human approval → action → outcome lifecycle.

## TypeScript / JavaScript SDK

```bash
npm install @cybertechsoft/loopgrid
```

```js
const { LoopGrid } = require('@cybertechsoft/loopgrid');
const lg = new LoopGrid({baseUrl:'http://localhost:8000', apiKey:process.env.LOOPGRID_SERVICE_KEY});

const d = await lg.recordDecision({
  decision_type:'customer_refund',
  agent:{id:'support-agent',version:'1.0'},
  authority:{acting_for:'Acme',limit_usd:1500,scope:['refund:create']},
  model:{provider:'openai',name:'gpt-5'},
  context:{prompt_version:'support-v1'},
  proposed_action:{tool:'stripe.refunds.create',amount:1000,currency:'USD'}
});
```

TypeScript declarations ship with the npm package.

## Independent verification

Export an evidence ZIP, then verify it without a running LoopGrid service:

```powershell
python verifier\loopgrid_verify.py evidence.zip
```

For stronger out-of-band signer identity verification:

```powershell
python verifier\loopgrid_verify.py evidence.zip --expected-key-id ed25519:...
```

Portable consistency proof and signer trust are separate concepts. A bundle can be internally valid while the verifier still needs an out-of-band reason to trust the signer identity.

## Privacy model

- **FULL** — raw disclosures encrypted separately; signed ledger stores commitment/reference.
- **REDACTED** — selected values replaced by commitments.
- **PROOF-ONLY** — only commitment/proof metadata retained.

Encrypted disclosures can be erased later without rewriting the signed evidence chain.


## OTLP/HTTP trace ingestion

LoopGrid accepts OTLP trace exports on the standard `/v1/traces` path using either:

- `Content-Type: application/x-protobuf` (recommended/default for many OpenTelemetry SDKs)
- `Content-Type: application/json`
- optional `Content-Encoding: gzip` for either encoding

Example environment configuration:

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:8000/v1/traces
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="X-LoopGrid-Key=lg_live_...,X-LoopGrid-Workspace=default"
```

A successful OTLP export returns the standard empty `ExportTraceServiceResponse`. The response header `X-LoopGrid-Accepted` reports how many spans were mapped into LoopGrid decisions. LoopGrid's OTLP adapter preserves both current `gen_ai.provider.name` and the older `gen_ai.system` provider attribute when present.

This ingestion compatibility does not change the LoopGrid evidence bundle, hash-chain, signing or offline-verifier contracts.

## Auth model

Service API-key scopes:

- `ingest`
- `read`
- `review`
- `admin`

Human roles:

- `owner`
- `admin`
- `reviewer`
- `viewer`

In production mode v0.8 refuses startup when auth is disabled or bootstrap/platform-admin secrets are missing/placeholder values.

## Supported integrations

Validated/foundation paths include REST, Python SDK, TypeScript/JavaScript SDK, OpenAI helper, Anthropic helper, LangGraph helper, OpenTelemetry/OTLP HTTP (protobuf + JSON) and allow-listed MCP proxy/ingestion.

The canonical LoopGrid evidence schema remains provider-neutral. Do not couple your historical evidence model to a single vendor's telemetry schema.

## Current validation posture

The frozen v0.7.2 baseline passed the core regression suite, real-scenario, API-key lifecycle, human RBAC, MCP gateway, live OpenAI and RFC3161 protocol/imprint gates. On 2026-09-03 that baseline also passed the PostgreSQL/Docker full real scenario plus app restart, PostgreSQL restart, signer persistence, decision persistence and workspace chain-continuity validation.

LoopGrid v0.8 then passed its full Windows/Docker design-partner deployment gate on 2026-09-03: PostgreSQL posture, production safety, anonymous-access blocking, scoped service identity creation/revocation, complete refund decision lifecycle, workspace cryptographic verification, tamper detection, signed checkpoint/head binding, signer-pinned offline verification, disclosure-withheld export and OTLP ingestion.

Rerun the included validators in each new deployment environment before making environment-specific claims.

## Explicit claim boundaries

Do **not** describe LoopGrid evidence as physically “immutable”; use **signed** and **tamper-evident**.

v0.8 does **not** by itself claim:

- Production GA or a production SLA;
- legal or regulatory compliance/certification;
- live hardware-backed AWS KMS signing unless exercised in that deployment;
- trusted RFC3161 TSA signer certificate-chain validation unless explicitly configured/tested;
- validated multi-instance horizontal scaling.

## Documentation

- `docs/DECISION_EVIDENCE_PROFILE_3.0.md`
- `docs/TRUST_MODEL.md`
- `docs/DEPLOYMENT.md`
- `docs/PILOT_SUCCESS_CRITERIA.md`
- `DESIGN_PARTNER_GUIDE.md`
- `SECURITY.md`
- `CHANGELOG.md`

## License

Apache 2.0.
