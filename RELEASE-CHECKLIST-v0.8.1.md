# LoopGrid v0.8.1 — OTLP Interoperability Release Checklist

This is a backward-compatible server-ingestion update from the public v0.8.0 Design Partner Release.
The evidence bundle, signing format, verifier contract, Python SDK API and JavaScript SDK API are intentionally unchanged.

## Before changing GitHub

- [ ] Keep the current public `main` as the rollback point. Do not delete or overwrite the existing `v0.8.0` tag/release if present.
- [ ] Upload the v0.8.1 changed/new files with their repository paths preserved.
- [ ] Confirm `app/version.py` reports `0.8.1-design-partner`.
- [ ] Confirm `sdk/python/pyproject.toml`, `sdk/python/loopgrid/__init__.py`, and `sdk/javascript/package.json` remain at `0.8.0` because the SDK package code did not change.
- [ ] Do not modify the separate `loopgridio/loopgrid-evidence-verify` Marketplace repository for this release.

## Required CI checks

- [ ] GitHub `tests` workflow is green for Python 3.10, 3.12 and 3.13.
- [ ] JavaScript SDK syntax / `npm pack --dry-run` job is green.
- [ ] Docker image build job is green.
- [ ] CodeQL workflow is green or has no blocking findings caused by this patch.
- [ ] Dependabot configuration is accepted by GitHub.

## OTLP acceptance checks

- [ ] OTLP/HTTP JSON request succeeds and returns `{}` with `Content-Type: application/json`.
- [ ] OTLP/HTTP protobuf request succeeds and returns an empty `ExportTraceServiceResponse` with `Content-Type: application/x-protobuf`.
- [ ] Gzipped protobuf request succeeds.
- [ ] Malformed protobuf is rejected cleanly.
- [ ] Unsupported content type/encoding is rejected cleanly.
- [ ] Decoded gzip body limit is enforced.
- [ ] JSON and protobuf inputs map equivalent semantic attributes into LoopGrid evidence.
- [ ] A standard OpenTelemetry Python OTLP/HTTP protobuf exporter can send a span successfully.
- [ ] Evidence generated from protobuf ingestion exports successfully and verifies with the existing LoopGrid offline verifier / GitHub Action v1.0.0 contract.

## Release

- [ ] Commit to `main` only after CI is green.
- [ ] Create a GitHub release/tag `v0.8.1` from the tested commit.
- [ ] Release note: OTLP/HTTP protobuf + JSON + gzip interoperability; no evidence-format change.
- [ ] Do **not** republish PyPI `loopgrid` or npm `@cybertechsoft/loopgrid` solely for this backend change.
- [ ] Rebuild any deployed/self-hosted Docker image from the new GitHub source.
- [ ] Update loopgrid.io integration/docs copy only after the public GitHub checks are green.

## Rollback

If GitHub CI or a deployment smoke test fails, revert the v0.8.1 commit(s) on `main` or redeploy the previously validated v0.8.0 source. Do not rewrite published tags.
