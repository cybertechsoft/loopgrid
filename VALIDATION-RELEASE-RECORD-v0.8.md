# LoopGrid v0.8.0 — Design Partner Release Validation Record

**Runtime:** `0.8.0-design-partner`  
**Evidence profile:** `3.0-draft`  
**Release posture:** Controlled design-partner technical evaluation  
**Production posture:** **Not Production GA**

## Executive determination

LoopGrid v0.8 packages the validated evidence-gateway baseline into a cleaner design-partner release with PostgreSQL-first Docker deployment, production-mode safety checks, refreshed Python/TypeScript SDKs, deployment validation tooling and current evidence-plane positioning.

The frozen v0.7.2 baseline passed its core regression and external-integration gates. On 2026-09-03 that baseline additionally passed a PostgreSQL/Docker full real scenario plus application restart, PostgreSQL restart, signer-key persistence, decision persistence and workspace chain-continuity validation.

v0.8 changes deployment configuration, documentation and SDK surfaces. Its final Windows/Docker target-machine deployment gate passed on 2026-09-03 with decision `dec_3a6824894bf74c0b8f89fd81`.

## Gate matrix

| Gate | State | Evidence / interpretation |
|---|---|---|
| v0.8 automated regression suite | PASS | 46 tests pass in the packaging environment. |
| Python SDK package build | PASS | `loopgrid` 0.8.0 wheel + sdist build successfully; wheel metadata and clean-target import smoke pass. |
| TypeScript/JavaScript package validation | PASS | Node syntax, `npm pack` and install/request-contract smoke pass. |
| AWS KMS adapter contract | PASS (local contract) | P-256 / SHA-256 DIGEST / ECDSA_SHA_256 contract verifies locally; not a live AWS IAM/KMS boundary. |
| v0.7.2 PostgreSQL/Docker deployment | PASS (baseline) | Full real scenario PASS; app restart, DB restart, signer persistence, decision persistence and workspace integrity PASS. Validation decision `dec_a75ad82d6063458eb77b8307`. |
| v0.8 production safety checks | PASS (automated) | Production-mode guard rejects placeholder/unsafe configuration and exposes deployment-security posture. |
| v0.8 Docker + PostgreSQL deployment validator | PENDING TARGET-MACHINE RUN | Run `powershell -ExecutionPolicy Bypass -File .\\validate_pilot.ps1`. Must end with `LOOPGRID v0.8 PILOT DEPLOYMENT VALIDATION: PASS`. |
| Live OpenAI | PASS on frozen v0.7.2 baseline | Live provider scenario previously passed; rerun only if making a v0.8-specific live-provider claim. |
| RFC3161 protocol/imprint + portable token | PASS on frozen v0.7.2 baseline | Live timestamp imprint and token preservation passed; trusted signer CA-chain verification remains separate. |
| Human RBAC / API-key lifecycle / MCP allow-list | PASS on frozen v0.7.2 baseline | Dedicated validation gates passed; v0.8 retains these paths and adds stricter production defaults. |
| Live AWS IAM/KMS hardware-backed boundary | DEFERRED | Do not claim live hardware-backed signing. |
| RFC3161 signer CA-chain trust | DEFERRED | Do not claim independent TSA signer-chain trust. |
| Multi-instance horizontal chain correctness | DEFERRED | Single-instance controlled design-partner topology only. |

## Supported public claims

The v0.8 target-machine deployment validator passed. The release can accurately state that it provides:

- verifiable evidence infrastructure for consequential AI and agent decisions;
- PostgreSQL-backed controlled design-partner deployment;
- signed, tamper-evident workspace-scoped evidence chains;
- persistent local Ed25519 signing for controlled evaluation;
- deterministic policy provenance and human-oversight evidence;
- action and observed-outcome evidence;
- portable evidence bundles with offline verification and signer pinning;
- FULL / REDACTED / PROOF-ONLY privacy modes with encrypted erasable disclosures;
- REST, Python, TypeScript/JavaScript, OTLP and allow-listed MCP integration paths;
- production-mode safety checks that require PostgreSQL, authentication and non-placeholder secrets.

## Explicit claim boundaries

Do not claim:

- Production GA, production SLA or broad production readiness;
- physical or legal “immutability” — use **signed / tamper-evident**;
- legal/regulatory compliance or certification;
- live hardware-backed AWS KMS unless actually exercised in the deployment;
- trusted RFC3161 signer certificate-chain validation unless separately exercised;
- validated multi-instance horizontal scaling;
- live Anthropic generation until a full provider scenario passes with available credits.

## Final v0.8 release gate

From a clean extracted release folder on the Windows/Docker evaluation machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\validate_pilot.ps1
```

Expected final line:

```text
LOOPGRID v0.8 PILOT DEPLOYMENT VALIDATION: PASS
```

The validated Windows/Docker run completed with the expected final PASS line on 2026-09-03. Rerun this gate in each new deployment environment before making environment-specific claims.
