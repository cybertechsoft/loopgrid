$ErrorActionPreference = "Stop"
Write-Host "LoopGrid v0.8 local validation" -ForegroundColor Cyan
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts\kms_contract_validation.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "LOCAL VALIDATION COMPLETE" -ForegroundColor Green
