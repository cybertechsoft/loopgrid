# LoopGrid v0.8.1 — OTLP Interoperability Validation Record

**Baseline:** public `cybertechsoft/loopgrid` download supplied on 2026-09-18  
**Runtime candidate:** `0.8.1-design-partner`  
**Evidence profile:** `3.0-draft`  
**Bundle contract:** `loopgrid/evidence-bundle/2` (unchanged)

## Validation completed in the build workspace

| Check | Result | Notes |
|---|---|---|
| Python test suite | PASS | 55 tests passed. |
| Python syntax compile | PASS | `app/*.py` and `verifier/*.py`. |
| JavaScript SDK syntax | PASS | `node --check sdk/javascript/index.js`. |
| UI JS syntax | PASS | `node --check app/static/app.js`. |
| npm dry-run pack | PASS | Existing SDK remains `@cybertechsoft/loopgrid@0.8.0`; 5 expected files only. |
| OTLP/HTTP JSON | PASS | Standard `{}` `ExportTraceServiceResponse` JSON body; accepted count in response header. |
| OTLP/HTTP protobuf | PASS | Binary `ExportTraceServiceRequest` accepted; binary `ExportTraceServiceResponse` returned. |
| OTLP gzip | PASS | Gzipped protobuf accepted. |
| Malformed protobuf | PASS | Clean 400 with protobuf `google.rpc.Status` body. |
| Unsupported media/encoding | PASS | Clean 415 responses. |
| Decompressed body limit | PASS | Oversized decoded gzip body rejected with 413. |
| JSON/protobuf mapping parity | PASS | Core decision/model/context/action attributes map equivalently. |
| Standard OpenTelemetry Python HTTP exporter | PASS | `opentelemetry-exporter-otlp-proto-http` successfully exported a real span to `/v1/traces`; LoopGrid recorded the expected provider, model, service and tool attributes. |
| Evidence after protobuf ingestion | PASS | Exported bundle verifies with the existing standalone verifier contract; Bundle v2 and Ed25519 unchanged. |
| Full external HTTP real-scenario validation | PASS | Complete decision lifecycle, policy, human review, action/outcome, chain verification, tamper detection, checkpoint, signer-pinned offline verification, withheld export and OTLP JSON ingestion all passed. |
| YAML parse | PASS | CI, Dependabot and CodeQL YAML parse successfully. |
| Docker build in this build workspace | NOT RUN | Docker CLI is not available in this environment. A Docker build job is included in GitHub CI and must be green before tagging `v0.8.1`. |
| CodeQL execution | NOT RUN LOCALLY | CodeQL workflow is included and must be green/triaged on GitHub before tagging. |

## Compatibility boundary

No changes were made to:

- Evidence Bundle v2 structure
- Evidence Profile `3.0-draft`
- Ed25519 signing semantics
- SHA-256 workspace chain semantics
- checkpoint representation
- standalone verifier behavior
- Python SDK package source/API
- JavaScript SDK package source/API
- GitHub Marketplace verifier Action `v1.0.0`

## Release gate

Do not tag `v0.8.1` until the pushed GitHub commit has green Python, JavaScript SDK and Docker jobs, and the CodeQL run has no new blocking finding caused by this patch.
