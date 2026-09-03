# LoopGrid v0.8 — Design Partner Guide

## What LoopGrid is

**LoopGrid is the evidence plane for AI agents.** It captures what a consequential agent was allowed to do, why it acted, what policy/human oversight applied, what external action occurred and what outcome was observed—then seals that lifecycle as portable, independently verifiable evidence.

## Best first workflow

Choose one workflow where an AI agent can change state or materially affect a customer: refund, account credit, claim, permission change, outbound action, escalation or similar.

## Evaluation path

1. Deploy locally with Docker Compose or point the SDK/REST client at an existing LoopGrid instance.
2. Create a workspace-scoped service identity.
3. Capture one consequential decision and append the lifecycle evidence.
4. Verify workspace integrity and export a disclosure-appropriate evidence ZIP.
5. Run the standalone verifier without relying on the LoopGrid service.
6. Review deployment gaps before any sensitive production use.

## Quick local deployment

```powershell
python scripts\generate_pilot_env.py
powershell -ExecutionPolicy Bypass -File .\validate_pilot.ps1
```

## What v0.8 is validated for

The release is intended for controlled design-partner technical evaluation. The v0.7.2 baseline passed the core regression, API-key, RBAC, MCP, live OpenAI, RFC3161 protocol/imprint and PostgreSQL persistence gates. v0.8 adds safer production-mode configuration and refreshed SDK/deployment tooling; run the included validators in the target environment before making deployment-specific claims.

## What we do not claim

- Production GA;
- physical immutability;
- legal/regulatory compliance by virtue of evidence integrity;
- live hardware-backed AWS KMS signing unless that deployment has actually exercised it;
- trusted TSA signer certificate-chain verification unless explicitly configured and tested.
