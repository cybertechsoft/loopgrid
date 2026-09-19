# Unreleased — Developer onboarding and container distribution

## Added

- Cross-platform `scripts/quickstart.py` local evaluation path using isolated SQLite state and a temporary local Ed25519 signer.
- Quickstart exports `demo-output/evidence.zip` and independently verifies it against an out-of-band trusted public key.
- GitHub Container Registry publishing workflow for `ghcr.io/cybertechsoft/loopgrid`.
- Multi-platform container builds for `linux/amd64` and `linux/arm64`.
- Docker build context hardening via `.dockerignore` so local secrets, keys, databases and generated artifacts are not copied into images.
- CI now smoke-tests container startup and the `/health` endpoint after building the image.
- `edge` container tag for tested `main`; future releases publish semantic-version and `latest` tags.

## Compatibility

- No evidence schema, signing, verifier, API, Python SDK or JavaScript SDK contract changes.
- GitHub Marketplace verifier `v1.0.0` remains compatible.

---

# LoopGrid v0.8.1 — OTLP Interoperability

## Added / changed

- `/v1/traces` accepts OTLP/HTTP binary protobuf (`application/x-protobuf`) in addition to JSON.
- OTLP/HTTP gzip request bodies are supported with decoded-size enforcement.
- JSON and protobuf requests share one normalized trace-to-evidence mapping.
- OTLP `AnyValue` parsing covers scalar, array, key/value-list and byte values.
- Successful OTLP responses use the standard `ExportTraceServiceResponse` encoding and mirror the request content type.
- `X-LoopGrid-Accepted` exposes the accepted-span count without adding non-standard fields to the OTLP response body.
- Added malformed-body, unsupported-media-type, gzip, parity and protobuf regression tests.
- CI updated to current GitHub Actions and multiple supported Python versions.
- Added Dependabot and CodeQL workflow configuration.

## Compatibility

- Evidence Bundle v2, Evidence Profile `3.0-draft`, signing, checkpoints and the standalone verifier are unchanged.
- GitHub Marketplace verifier `v1.0.0` does not require an update for this server-ingestion change.
- Python and JavaScript SDK package APIs remain `0.8.0`; they are not republished unless their package code changes.

---

# LoopGrid v0.8.0 — Design Partner Release

## Focus

v0.8 turns the validated Evidence Gateway baseline into a simpler, safer design-partner release without adding cloud-account or payment requirements.

## Added / changed

- Runtime version `0.8.0-design-partner`.
- Production-mode startup safety guard: PostgreSQL, auth-required mode, strong bootstrap/platform-admin secrets, non-wildcard CORS and valid request-size limits.
- Configurable restricted CORS; no wildcard default.
- Docker Compose no longer ships hard-coded pilot passwords/secrets.
- `scripts/generate_pilot_env.py` generates strong local `.env` secrets without printing them.
- `validate_pilot.ps1` + `scripts/pilot_deployment_validation.py` provide a one-command Docker/PostgreSQL release gate.
- Python SDK version 0.8.0 with evidence-lifecycle convenience methods and PyPI build metadata.
- npm package aligned to `@cybertechsoft/loopgrid` version 0.8.0 with TypeScript declarations.
- Evidence Profile 3.0 examples, deployment guide, trust model and pilot success criteria.
- Public positioning standardized on “the evidence plane for AI agents” and “signed / tamper-evident evidence.”

## Intentionally deferred

Live AWS KMS, TSA certificate-chain trust, multi-instance concurrency, advanced key rotation and enterprise monitoring remain later hardening work and do not block controlled design-partner evaluation.

### Pre-release Windows CLI compatibility fix
- Validation-script console output is now ASCII-safe on Windows code pages (for example CP1252).
- Replaced Unicode comparison/em-dash characters in CLI validation output to prevent `charmap` encoding failures under PowerShell subprocess capture.
- No runtime API, evidence format, or cryptographic behavior changed.

### Pre-release standalone-verifier dependency fix
- Pilot validation now detects whether the host Python can run the standalone verifier.
- When verifier dependencies are absent, the validator creates an isolated temporary verifier environment and installs only `cryptography` and `asn1crypto` there.
- The host Python environment is left unchanged.
- Scenario and temporary admin service identities are revoked during cleanup.
- Final Windows/Docker pilot deployment validation passed on 2026-09-03.
