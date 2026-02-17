# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Email **security@loopgrid.dev** or open a private security advisory on GitHub.

## Security Features

### Hash Chain Integrity
All decisions are cryptographically hashed (SHA-256) and chained. Tampering with any record breaks the chain and is detectable via `GET /v1/integrity/verify`.

### Current V1 Limitations

LoopGrid V1 is designed for **local development and small-scale deployments**. It does not include:
- Authentication / Authorization
- API key management
- Rate limiting
- Encrypted storage

### For Production Use

1. Run behind a reverse proxy (nginx, Traefik) with TLS
2. Add authentication at the proxy level
3. Restrict network access to trusted services
4. Use PostgreSQL instead of SQLite
5. Enable audit logging at the infrastructure level
6. Set API keys via environment variables (never in code)

---

**Note:** V2 will include built-in authentication and security features.
