# LoopGrid v0.4.0 Pilot — Changelog

## Product/UI
- Replaced the generic dark AI-SaaS visual style with a light evidence-desk interface.
- New editorial/technical hierarchy, denser decision register, restrained color system and clearer cryptographic posture.
- Updated decision drawer, proof lab, replay comparison, evidence page and integration page.

## Evidence architecture
- Chains are now isolated per workspace rather than globally across every tenant.
- Evidence Profile bumped to `loopgrid/1.1-draft`.
- Privacy metadata and payload commitments are included in signed event bodies.
- Portable verifier now treats cryptographic chain continuity as the invariant rather than global database sequence adjacency.

## Customer-pilot functionality
- Workspace model and workspace-scoped API keys.
- API keys stored as one-way SHA-256 digests; raw secret shown once.
- Idempotent decision/event ingestion.
- `full`, `redacted`, and `proof_only` privacy modes.
- OpenTelemetry-style GenAI span ingestion.
- Signed workspace checkpoint attestation endpoint.
- Python/JavaScript SDK upgrades.

## Trust & security accuracy
- External trusted timestamp remains explicitly unconfigured in the pilot.
- Checkpoints use the local signer and local clock; they must not be represented as third-party timestamps.
- Evidence reports continue to state that integrity verification is not itself a legal compliance determination.

## Quality
- 10 automated regression tests.
- Python compilation and JavaScript syntax validation pass.
