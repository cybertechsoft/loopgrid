# LoopGrid v0.8 Design-Partner Deployment

The default v0.8 pilot topology is intentionally small: **LoopGrid + PostgreSQL**, both run with Docker Compose. No cloud account is required.

## Quick start

```powershell
python scripts\generate_pilot_env.py
docker compose up --build -d
docker compose ps
```

The generator creates strong local secrets in `.env` and does **not** print them. `.env` is ignored by Git.

Validate the complete deployment:

```powershell
powershell -ExecutionPolicy Bypass -File .\validate_pilot.ps1
```

The validator checks PostgreSQL, production safety posture, anonymous-access denial and the full consequential-decision/evidence scenario.

## Production-mode safety guard

When `LOOPGRID_ENV=production` and `LOOPGRID_STRICT_PRODUCTION_SAFETY=true`, LoopGrid refuses startup if any of these are unsafe:

- database is not PostgreSQL;
- human authentication is disabled;
- platform-admin secret is missing/placeholder/too short;
- bootstrap token is missing/placeholder/too short;
- CORS contains wildcard `*`;
- request-body limit is invalid.

This is a controlled **design-partner** deployment posture, not a claim of Production GA.

## Persistence

Compose uses named volumes for PostgreSQL data and local signing-key material. Normal restarts preserve both. Do not run `docker compose down -v` unless you intentionally want to destroy local pilot data.

## Optional integrations

RFC3161 TSA and AWS KMS remain optional trust-boundary integrations. The v0.8 design-partner release does not require creating or paying for those services.
