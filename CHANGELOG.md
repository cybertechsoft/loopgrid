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
