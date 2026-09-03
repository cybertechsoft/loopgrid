# LoopGrid Trust Model — v0.8

LoopGrid produces **signed, tamper-evident evidence** for consequential AI/agent decisions. It does not claim that records are physically immutable, and evidence integrity alone is not a legal compliance determination.

## Evidence captured

A complete decision can preserve:

1. agent identity and version;
2. delegated authority/scope;
3. model and context provenance;
4. deterministic policy identity/version/digest/result;
5. human review/adjudication;
6. tool/action evidence;
7. observed outcome;
8. cryptographic content commitments, workspace chain and signer identity.

## Cryptographic boundary

The default design-partner deployment uses persistent local Ed25519 signing and SHA-256 workspace-scoped hash chains. Portable bundles can be verified offline and can pin the expected signer key identity.

AWS KMS support exists as a separate optional hardened signing path; live hardware-backed KMS validation is **not** a prerequisite or claim of this v0.8 release.

## Privacy

FULL disclosures are encrypted separately from the signed ledger. REDACTED and PROOF-ONLY modes reduce stored content. Encrypted disclosure payloads can be erased without rewriting the signed commitment history.

## External timestamping

RFC3161 timestamp protocol/imprint capture is supported. Certificate-chain trust for a chosen TSA remains a separate deployment decision and must not be implied merely because a timestamp token exists.

## Authentication

Service API keys are workspace-scoped and permissioned (`ingest`, `read`, `review`, `admin`). Human sessions use workspace roles (`owner`, `admin`, `reviewer`, `viewer`). Production-mode startup requires auth and strong bootstrap/platform-admin secrets.
