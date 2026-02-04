#!/usr/bin/env python3
"""
LoopGrid Example: Basic Usage
=============================

This example shows the basic workflow:
1. Record a decision
2. Mark as incorrect
3. Create replay
4. Attach correction

Run:
    python examples/01_basic_usage.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))

from loopgrid import LoopGrid

# Initialize
grid = LoopGrid(service_name="demo-agent")

# Check connection
try:
    health = grid.health()
    print(f"✓ Connected to LoopGrid {health.get('version')}")
except Exception as e:
    print(f"✗ Start server first: python run_server.py")
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

# Mark as incorrect
print("\n2. Marking as incorrect...")
grid.mark_incorrect(decision["decision_id"], reason="Missed billing issue")
print("   ✓ Marked")

# Create replay
print("\n3. Creating replay...")
replay = grid.create_replay(
    decision_id=decision["decision_id"],
    overrides={"prompt": {"template": "support_v2"}}
)
print(f"   Replay ID: {replay['replay_id']}")
print(f"   Output changed: {replay['output_changed']}")

# Attach correction
print("\n4. Attaching correction...")
grid.attach_correction(
    decision_id=decision["decision_id"],
    correction={"response": "I see the duplicate charge. Refund initiated."},
    corrected_by="agent_42"
)
print("   ✓ Correction attached")

print("\n✓ Demo complete!")
