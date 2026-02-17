#!/usr/bin/env python3
"""
LoopGrid Example: Basic Usage
Run: python examples/01_basic_usage.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))

from loopgrid import LoopGrid

grid = LoopGrid(service_name="demo-agent")

try:
    health = grid.health()
    print(f"✓ Connected to LoopGrid {health.get('version')}")
except Exception:
    print("✗ Start server first: python run_server.py")
    sys.exit(1)

# Record a decision
print("\n1. Recording decision...")
decision = grid.record_decision(
    decision_type="customer_support_reply",
    input={"message": "I was charged twice"},
    model={"provider": "openai", "name": "gpt-4"},
    output={"response": "Your account looks fine."}
)
print(f"   Decision ID: {decision['decision_id']}")
print(f"   Content hash: {decision['content_hash'][:16]}...")

# Mark as incorrect
print("\n2. Marking as incorrect...")
grid.mark_incorrect(decision["decision_id"], reason="Missed billing issue")

# Create replay
print("\n3. Creating replay...")
replay = grid.create_replay(
    decision_id=decision["decision_id"],
    overrides={"prompt": {"template": "support_v2"}}
)
print(f"   Replay ID: {replay['replay_id']}")
print(f"   Mode: {replay.get('execution_mode', 'unknown')}")
print(f"   Output changed: {replay['output_changed']}")

# Attach correction
print("\n4. Attaching correction...")
grid.attach_correction(
    decision_id=decision["decision_id"],
    correction={"response": "I see the duplicate charge. Refund initiated."},
    corrected_by="agent_42"
)

# Verify integrity
print("\n5. Verifying ledger integrity...")
integrity = grid.verify_integrity()
print(f"   {integrity['integrity']['message']}")

# Compliance report
print("\n6. Generating compliance report...")
report = grid.compliance_report()
art12 = report["eu_ai_act_mapping"]["article_12_record_keeping"]["status"]
print(f"   EU AI Act Article 12: {art12}")

print("\n✓ Demo complete!")
