# LoopGrid v0.7 — Evidence Gateway

## Added
- Evidence Profile `3.0-draft` and documented canonical decision/evidence model.
- Deterministic lifecycle projection and consequential event-order enforcement.
- Deterministic `policy_digest` and evaluation `input_commitment`.
- API-key descriptions, expiry, status metadata and atomic replacement-key rotation.
- Usage metering with `consequential_decision` as the planned billing unit.
- PostgreSQL per-workspace chain-head serialization and configurable pooling.
- Evidence Bundle v2: signer, verification, lifecycle and policy artifacts.
- Offline verifier v2 consistency checks for the new bundle artifacts.
- Request body-size guard and expanded system/pilot posture reporting.

## Changed
- Idempotent event retries are resolved before lifecycle validation.
- Policy and lifecycle provenance are explicit in API/OpenAPI responses.
- SDK/runtime version metadata advanced to 0.7.0.

## Validation
- 39 automated tests pass.
- State-safe external HTTP real-scenario test passes using localhost, local Ed25519, SQLite and deterministic provider/tool doubles.

## Still pending live external validation
- PostgreSQL/Docker on the target Windows development machine.
- OpenAI and Anthropic provider calls.
- Configured MCP proxy against the local fake server / real tool service.
- AWS KMS signer boundary.
- External RFC 3161 TSA trust chain.
