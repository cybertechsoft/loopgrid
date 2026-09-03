# LoopGrid v0.7.2 — Consolidated Clean Validation Build

This build consolidates the validated v0.7 hotfixes into one clean package. It contains no
`local-backups`, `__pycache__`, `.pytest_cache`, test databases, or generated local secrets.

## Consolidated fixes

- Windows-safe standalone verifier output and deterministic UTF-8 subprocess handling.
- API-key issuance respects the human/service admin authorization boundary when auth is required.
- MCP gateway validation utility and human RBAC validation utility included.
- RFC3161 parser fixed for `asn1crypto 1.5.x` (`EncapsulatedContentInfo.content.parsed`).
- RFC3161 capture validates SHA-256 imprint and the request nonce before reporting an external timestamp.
- Evidence export only attaches a checkpoint that covers the target decision and includes proof-only
  bridge witnesses through a later covering checkpoint.
- Portable verifier validates checkpoint signatures and RFC3161 token imprints without requiring OpenSSL.
  OpenSSL + `--tsa-ca-file` remains optional for TSA certificate-chain trust validation.
- Pilot readiness no longer marks external timestamping PASS merely because a TSA URL is configured;
  it requires an observed successful externally timestamped checkpoint.
- Real-scenario runner checkpoints the target decision before export, asserts direct decision-head binding,
  and asserts `timestamp.tsr` when an external timestamp succeeds.
- Pytest is isolated from ambient TSA configuration and restricted to the `tests/` tree.
- Test SQLAlchemy engine is disposed at process exit to avoid Windows temporary SQLite cleanup warnings.
- Local AWS KMS P-256/ECDSA contract validation and direct TSA validation scripts included.

## Validation claim boundaries

- Local/core workflow, API-key security, human RBAC, MCP, live OpenAI, RFC3161 protocol/imprint and
  local AWS KMS contract have been exercised during v0.7 validation work.
- Live Anthropic generation remains deferred until API credits are available.
- Live AWS IAM/KMS hardware-backed signing remains deferred until a real AWS account boundary is exercised.
- TSA certificate-chain trust remains separate from protocol/imprint validation and requires a trusted CA bundle.
- PostgreSQL/Docker remains a separate deployment gate.
