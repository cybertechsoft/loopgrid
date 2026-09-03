$ErrorActionPreference = "Stop"
Write-Host "LoopGrid v0.8 Design Partner Release - Docker validation"
if (-not (Test-Path ".env")) {
  Write-Host "No .env found. Generating strong local deployment secrets..."
  python scripts\generate_pilot_env.py
}
Write-Host "Validating Compose configuration..."
docker compose config --quiet
Write-Host "Starting PostgreSQL + LoopGrid..."
docker compose up --build -d
Write-Host "Waiting for healthy containers..."
Start-Sleep -Seconds 5
docker compose ps
python scripts\pilot_deployment_validation.py --env-file .env --output-dir pilot-validation-output-v080
