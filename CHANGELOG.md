# Changelog

## v0.1.0 (2025-02-17)

### Added
- Decision Ledger with cryptographic hash chain (SHA-256)
- Replay Engine with live LLM execution (OpenAI, Anthropic) and simulation fallback
- Human Correction Loop with ground truth capture
- Ledger integrity verification endpoint
- EU AI Act compliance report generator (JSON + HTML)
- Decision export (JSON + CSV)
- Python SDK with full API coverage
- JavaScript SDK (npm: @cybertechsoft/loopgrid)
- FastAPI backend with OpenAPI docs
- Test suite (pytest)
- Docker support
- Landing page

### Architecture
- Immutable decision records with SHA-256 content hash + chain hash
- Live LLM replay via OpenAI/Anthropic APIs (falls back to simulation)
- Compliance mapping to EU AI Act Articles 12, 14, 9
