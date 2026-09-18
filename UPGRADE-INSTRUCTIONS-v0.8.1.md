# Safe upgrade instructions — public LoopGrid v0.8.0 → v0.8.1

The patch was built from the direct GitHub `loopgrid-main.zip` baseline supplied on 2026-09-18. Do not delete the current repository or overwrite any published tag.

## Files to add

- `.github/dependabot.yml`
- `.github/workflows/codeql.yml`
- `app/otlp.py`
- `tests/test_otlp_http.py`
- `RELEASE-CHECKLIST-v0.8.1.md`
- `VALIDATION-RELEASE-RECORD-v0.8.1.md`
- `UPGRADE-INSTRUCTIONS-v0.8.1.md`

## Existing files to replace

- `.github/workflows/tests.yml`
- `CHANGELOG.md`
- `README.md`
- `app/main.py`
- `app/schemas.py`
- `app/static/app.js`
- `app/static/index.html`
- `app/version.py`
- `requirements.txt`
- `scripts/real_scenario_test.py`
- `tests/test_flow.py`

## Files that must NOT be changed for this release

- `verifier/loopgrid_verify.py`
- `sdk/python/pyproject.toml`
- `sdk/python/loopgrid/__init__.py`
- `sdk/python/loopgrid/client.py`
- `sdk/javascript/package.json`
- `sdk/javascript/index.js`
- `sdk/javascript/index.d.ts`
- evidence-profile and bundle-format documents/schemas unless a separate reviewed change is intended

The Python and JavaScript SDK packages therefore stay at `0.8.0`. The server runtime becomes `0.8.1-design-partner`.

## Safest GitHub update sequence

1. Confirm the current public repository is still `cybertechsoft/loopgrid` and keep the downloaded `loopgrid-main.zip` as rollback backup.
2. Apply only the files listed above, preserving their exact repository paths.
3. Commit with a message such as `Add OTLP HTTP protobuf interoperability`.
4. Open **Actions** immediately after the commit. Do not create a release yet.
5. Wait for the `tests` workflow and `CodeQL` workflow to finish.
6. Confirm all Python matrix jobs, JavaScript SDK job and Docker build job are green.
7. If any job is red, stop and fix/revert before tagging. The existing public v0.8.0 release remains the rollback baseline.
8. When green, test `/health` and confirm the runtime reports `0.8.1-design-partner`.
9. Run one OTLP JSON request and one standard OTLP/HTTP protobuf exporter request against the deployment being evaluated.
10. Export evidence from the protobuf-created decision and verify it with the existing `loopgrid-evidence-verify@v1.0.0` Action or the unchanged standalone verifier.
11. Only then create the GitHub release/tag `v0.8.1`.
12. Do not publish new PyPI/npm versions unless SDK package code is intentionally changed later.

## Website update timing

Do not update the live website first. After GitHub v0.8.1 is green and validated, update the website integration/docs copy from `OTLP/HTTP JSON` to `OTLP/HTTP protobuf + JSON`, and document gzip support. No website claim should say every OpenTelemetry framework has been validated unless it has actually been tested.
