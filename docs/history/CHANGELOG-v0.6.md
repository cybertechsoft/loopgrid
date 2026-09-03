# LoopGrid v0.6.0 — External Design Partner Release

## Trust / cryptography
- Centralized runtime, evidence-profile and product-stage version metadata.
- Added pluggable signing abstraction.
- Retained local Ed25519 signer for zero-setup evaluation.
- Added AWS KMS ECDSA P-256 signing path for reviewed cloud pilots.
- Added persistent signed workspace checkpoints.
- Added optional RFC 3161 timestamp-authority requests with message-imprint validation.
- Extended offline verifier to Ed25519/ECDSA, disclosures, chain witnesses and optional RFC 3161 CA validation.
- Evidence profile advanced to `2.0-draft`.

## Data minimization / retention
- FULL raw payloads moved out of signed event bodies into a separate AES-256-GCM encrypted disclosure vault.
- Signed evidence stores commitment + disclosure descriptor/reference.
- Added payload-status API.
- Added disclosure erasure while preserving signed evidence integrity.
- Added retention runner for expired encrypted disclosure payloads.
- Added disclosure-withheld evidence export (`include_payloads=false`).
- Fixed report/export path so a withheld bundle does not leak FULL raw payloads through `report.html`.

## Identity / authorization
- Added local human user accounts and password hashing.
- Added workspace memberships and owner/admin/reviewer/viewer roles.
- Added bearer sessions with expiry and logout.
- Added production bootstrap-token protection option.
- Hardened authorization so explicitly invalid or under-scoped credentials cannot fall through to local-demo bypass.

## API / documentation
- Added typed OpenAPI response models for principal endpoints.
- Added tagged API groups for Operations, Workspaces, Policies, Decisions, Reviews, Ingestion, Evidence, Replay and Demo.
- Added OpenAPI API-key and bearer-session security schemes.
- Added `/api/v1/system/info` trust-posture endpoint.
- Added request-safe bearer ContextVar cleanup on exception paths.

## Agent/runtime integrations
- Added OTLP/HTTP JSON pilot receiver path.
- Added allow-listed configured MCP HTTP JSON-RPC proxy/capture.
- Added richer OpenAI/Anthropic/LangGraph capture helpers for latency, usage, tool requests and errors.

## Operations
- Added per-process ingest/admin rate limiting.
- Expanded readiness/metrics information.
- Updated Docker/PostgreSQL pilot configuration.
- Added Trust page showing signer, disclosure vault, timestamp, access/RBAC and proxy posture.

## Validation
- Regression suite expanded to **28 tests**.
- Includes evidence export without disclosure leakage, payload erasure + proof preservation, retention, RBAC, typed OpenAPI, checkpoint persistence, MCP allow-list enforcement and provider-wrapper evidence tests.

## Known boundaries
- No complete enterprise OIDC/SAML SSO yet.
- No automatic multi-generation signing-key rotation/verification registry yet.
- Rate limiter is process-local, not distributed.
- OTLP is HTTP/JSON pilot support, not a complete collector/protobuf/gRPC implementation.
- MCP proxy is configured HTTP JSON-RPC alias mode, not every MCP transport.
- AWS KMS/TSA paths require validation in the customer's actual cloud/trust environment.
- Deterministic canonicalization is a LoopGrid draft profile; no formal RFC 8785 certification is claimed.
