# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in LoopGrid, please report it by emailing **security@loopgrid.dev** (or open a private security advisory on GitHub).

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

## Security Considerations

### Current V1 Limitations

LoopGrid V1 is designed for **local development and small-scale deployments**. It does not include:

- Authentication / Authorization
- API key management
- Rate limiting
- Input sanitization (beyond Pydantic validation)
- Encrypted storage

### For Production Use

If deploying LoopGrid in production, consider:

1. **Run behind a reverse proxy** (nginx, Traefik) with TLS
2. **Add authentication** at the proxy level
3. **Restrict network access** to trusted services only
4. **Use PostgreSQL** instead of SQLite for data integrity
5. **Enable audit logging** at the infrastructure level

### Data Privacy

LoopGrid stores AI decision data including:
- Input context
- AI outputs
- Human corrections

Ensure you comply with your organization's data policies and applicable regulations (GDPR, CCPA, etc.) when storing AI decision data.

---

**Note:** V2 will include built-in authentication and security features.
