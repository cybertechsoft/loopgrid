# LoopGrid Python SDK

LoopGrid is the **evidence plane for AI agents**. The SDK captures the decision lifecycle—agent identity, delegated authority, model/context, policy, human oversight, tool/action and observed outcome—and exports signed, tamper-evident evidence.

```bash
pip install loopgrid
```

```python
from loopgrid import LoopGrid

lg = LoopGrid(base_url="http://localhost:8000", api_key="lg_live_...")

d = lg.record_decision(
    decision_type="customer_refund",
    agent={"id": "support-agent", "version": "1.0"},
    authority={"acting_for": "Acme", "limit_usd": 1500, "scope": ["refund:create"]},
    model={"provider": "openai", "name": "gpt-5"},
    context={"prompt_version": "support-v1"},
    proposed_action={"tool": "stripe.refunds.create", "amount": 720, "currency": "USD"},
)

print(d["decision_id"])
print(lg.verify_workspace())
```

The v0.8 package is a **design-partner release**, not Production GA. Signed/tamper-evident evidence is not a legal compliance determination.
