# LoopGrid v0.8 Security Posture

LoopGrid v0.8 is a **controlled design-partner release**, not Production GA. This document describes implemented controls and explicit trust boundaries; it is not a certification or legal compliance statement.

## Implemented controls

- Workspace-scoped service API keys stored only by SHA-256 digest.
- Service-key scopes: `ingest`, `read`, `review`, `admin`.
- Key expiry metadata, revocation and replacement-key rotation.
- Human session authentication with scrypt password hashing.
- Workspace roles: owner/admin/reviewer/viewer.
- Production-mode startup guard requiring PostgreSQL, auth-required mode and strong bootstrap/platform-admin secrets.
- Configurable CORS with wildcard rejected in strict production mode.
- Request-size limit and in-process write rate limiting.
- Request IDs and security response headers.
- SHA-256 content commitments and workspace-scoped hash chain.
- Persistent Ed25519 signing in the default design-partner topology.
- Signed checkpoints.
- Evidence Bundle v2 with offline verification and optional signer pinning.
- AES-256-GCM encrypted FULL-disclosure vault separated from the signed ledger.
- Retention/erasure path that removes encrypted disclosures without rewriting signed commitments.
- Lifecycle enforcement for consequential event ordering.
- MCP proxy restricted to configured upstream aliases; arbitrary target URLs are rejected.

## PostgreSQL chain append behavior

On PostgreSQL, the ledger serializes workspace chain-head appends through database locking before selecting the predecessor. This is intended to prevent normal same-workspace writers from legitimately creating parallel children of one chain head. The v0.8 design-partner release does not claim a fully validated multi-instance/horizontal-scaling topology until a dedicated multi-instance gate is run.

## Platform bootstrap secret vs service identity

`LOOPGRID_PLATFORM_ADMIN_KEY` is a deployment bootstrap/administrative secret. It is **not** accepted as a normal evidence read/ingest/review credential. Normal integrations should use workspace-scoped service keys or human bearer sessions.

`LOOPGRID_BOOTSTRAP_TOKEN` is used only to create the first owner account in production mode; the endpoint becomes unavailable after the first user exists.

## Signing trust boundary

Default v0.8 design-partner deployments use a persistent local Ed25519 key. This provides cryptographic signatures and tamper evidence, but it is not represented as a hardware-backed production key-management boundary.

An AWS KMS asymmetric signing path exists separately. Do not claim live hardware-backed signing until the actual IAM/KMS boundary has been exercised in the target deployment.

## Timestamping

RFC3161 support validates timestamp imprint/nonce capture and can preserve `timestamp.tsr` in an evidence bundle. Trusting the TSA signer certificate chain is a separate assertion and should only be claimed after explicit CA-chain validation.

## Secrets

For Docker design-partner deployments use:

```powershell
python scripts\generate_pilot_env.py
```

The generated `.env` contains secrets and is gitignored. Do not paste or commit it. Rotate credentials before transferring a deployment to another organization.

## Logging

Do not add raw API keys, bearer sessions, provider API secrets or decrypted customer disclosures to application logs. Request IDs, key IDs/prefixes and evidence IDs are preferred for troubleshooting.

## Known/deferred hardening

- live managed/hardware-backed signer boundary;
- TSA signer certificate-chain trust for a chosen provider;
- dedicated multi-instance concurrency validation;
- complete multi-generation evidence-signing key rotation/anchoring policy;
- enterprise SSO/SAML;
- external distributed rate limiter;
- production monitoring/SIEM integration and SLA;
- independent penetration test/security audit.

## Language / claims

Use **signed / tamper-evident evidence**, not “immutable.” Evidence integrity can support governance, audit and regulatory workflows but does not itself prove HIPAA, GDPR, EU AI Act, SOC 2 or other compliance/certification.
