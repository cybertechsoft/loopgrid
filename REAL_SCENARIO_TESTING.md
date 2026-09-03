# LoopGrid v0.8 — Real Scenario & Deployment Validation

## Local application regression

```powershell
powershell -ExecutionPolicy Bypass -File .\validate_local.ps1
```

## Existing server real scenario

For development/no-auth mode:

```powershell
python scripts\real_scenario_test.py --output-dir real-test-output-v080
```

For an auth-required deployment pass a real admin-scoped service API key:

```powershell
python scripts\real_scenario_test.py --admin-key $adminServiceKey --output-dir real-test-output-v080
```

The platform bootstrap key is intentionally not a normal admin-scoped service identity for checkpoint/evidence operations.

## One-command Docker/PostgreSQL design-partner gate

```powershell
powershell -ExecutionPolicy Bypass -File .\validate_pilot.ps1
```

If `.env` is absent, the script generates secure local deployment secrets. It then validates Compose, starts PostgreSQL + LoopGrid and runs `scripts/pilot_deployment_validation.py`, which verifies:

- readiness;
- PostgreSQL provider;
- strict production safety posture;
- anonymous evidence access denial;
- temporary admin service identity issuance;
- full decision → model → policy → human review → action → outcome lifecycle;
- workspace crypto verification;
- tamper detection;
- signed checkpoint binding;
- portable evidence export and standalone verifier;
- disclosure-withheld export;
- OTLP ingestion;
- cleanup/revocation of the temporary validation key.

## Live model provider (optional)

OpenAI:

```powershell
$env:OPENAI_API_KEY="..."
$env:LOOPGRID_TEST_OPENAI_MODEL="..."
python scripts\real_scenario_test.py --provider openai --admin-key $adminServiceKey --output-dir live-openai-v080
```

Anthropic is equivalent with `ANTHROPIC_API_KEY` and `LOOPGRID_TEST_ANTHROPIC_MODEL`.

Do not paste provider secrets into chat or commit them to the repository.
