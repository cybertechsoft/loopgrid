# LoopGrid v0.5.0 — Design Partner Edition

## Product/UI
- Raised operational typography across sidebar, tables, evidence cards, drawer, code examples and mobile layouts.
- Added Review Queue and Policy Registry as first-class product surfaces.
- Preserved the restrained editorial/technical visual identity introduced in v0.4.
- Added richer integration documentation for native capture, OTLP/HTTP and MCP.

## Core platform
- Added versioned policy registry and deterministic amount-threshold evaluator.
- Added signed human review approve/reject workflow.
- Added scoped and revocable workspace API keys.
- Added workspace custom redaction paths and retention metadata.
- Added administrative audit log.
- Added OTLP/HTTP JSON trace ingestion at `/v1/traces`.
- Added MCP JSON-RPC ingestion at `/api/v1/ingest/mcp`.
- Added explicit OpenAI/Anthropic provider adapters and LangGraph/LangChain callback-style adapter.
- Added `/ready`, `/metrics`, request IDs, no-store API caching and baseline security headers.
- Added forward-only v0.4 → v0.5 local schema compatibility migration.

## Evidence
- Evidence profile upgraded to `1.2-draft`.
- Manifest now includes software version, capture source, policy reference and timestamping state.
- Human-readable evidence report redesigned to match the product's evidence-first visual identity.
- Existing workspace chain, witnesses, tamper detection, replay and offline verification retained.

## Validation
- 19 automated tests pass.
- Python compilation passes.
- JavaScript syntax check passes.
- Post-replay evidence export independently verifies.
