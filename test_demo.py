#!/usr/bin/env python3
"""
LoopGrid Demo
=============

Demonstrates the complete LoopGrid workflow:
1. Record an AI decision
2. View in ledger
3. Mark as incorrect
4. Create replay with improved prompt
5. Compare outputs
6. Attach human correction

Prerequisites:
    1. Start the server: python run_server.py
    2. Run this demo: python test_demo.py
"""

import sys
import os

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sdk', 'python'))

from loopgrid import LoopGrid, LoopGridError


def main():
    print()
    print("=" * 60)
    print("  LoopGrid Demo")
    print("  Control Plane for AI Decision Reliability")
    print("=" * 60)
    print()
    
    # Initialize client
    grid = LoopGrid(
        base_url="http://localhost:8000",
        service_name="support-agent"
    )
    
    # Check connection
    try:
        health = grid.health()
        print(f"✓ Connected to LoopGrid ({health.get('version', 'unknown')})")
    except LoopGridError as e:
        print(f"✗ Cannot connect: {e}")
        print()
        print("  Make sure the server is running:")
        print("  python run_server.py")
        return 1
    
    print()
    
    # ================================================================
    # STEP 1: Record Decision (with wrong output)
    # ================================================================
    
    print("─" * 60)
    print("STEP 1: Record AI Decision (WRONG)")
    print("─" * 60)
    print()
    print("  Customer: 'I was charged twice for my subscription'")
    print("  AI says:  'Your account looks fine to me.'")
    print()
    
    decision = grid.record_decision(
        decision_type="customer_support_reply",
        input={
            "message": "I was charged twice for my subscription",
            "customer_id": "cust_123",
            "conversation_id": "conv_456"
        },
        model={
            "provider": "openai",
            "name": "gpt-4",
            "version": "2024-01"
        },
        prompt={
            "template": "support_v1",
            "text": "You are a helpful support agent. Answer the customer's question."
        },
        output={
            "response": "Your account looks fine to me. Is there anything else I can help with?"
        },
        metadata={
            "latency_ms": 1240,
            "tokens": 150
        }
    )
    
    decision_id = decision["decision_id"]
    print(f"  ✓ Decision recorded: {decision_id}")
    print()
    
    # ================================================================
    # STEP 2: View in Ledger
    # ================================================================
    
    print("─" * 60)
    print("STEP 2: View Decision in Ledger")
    print("─" * 60)
    print()
    
    stored = grid.get_decision(decision_id)
    print(f"  ID:      {stored['decision_id']}")
    print(f"  Type:    {stored['decision_type']}")
    print(f"  Status:  {stored['status']}")
    print(f"  Input:   {stored['input']['message'][:50]}...")
    print(f"  Output:  {stored['output']['response'][:50]}...")
    print()
    
    # ================================================================
    # STEP 3: Mark as Incorrect
    # ================================================================
    
    print("─" * 60)
    print("STEP 3: Mark Decision as INCORRECT")
    print("─" * 60)
    print()
    
    updated = grid.mark_incorrect(
        decision_id=decision_id,
        reason="AI missed the duplicate charge - customer was charged twice"
    )
    
    print(f"  ✓ Status changed to: {updated['status']}")
    print(f"  Reason: {updated.get('incorrect_reason', 'N/A')}")
    print()
    
    # ================================================================
    # STEP 4: Create Replay with Better Prompt
    # ================================================================
    
    print("─" * 60)
    print("STEP 4: Create REPLAY with Improved Prompt")
    print("─" * 60)
    print()
    print("  Replaying with 'support_v2' prompt...")
    print("  (v2 includes: 'Always check for billing issues first')")
    print()
    
    replay = grid.create_replay(
        decision_id=decision_id,
        overrides={
            "prompt": {
                "template": "support_v2",
                "text": "You are a helpful support agent. ALWAYS check for billing issues like duplicate charges first. Acknowledge problems directly."
            }
        },
        triggered_by="human_review"
    )
    
    replay_id = replay["replay_id"]
    print(f"  ✓ Replay created: {replay_id}")
    print(f"  Output changed: {replay['output_changed']}")
    print()
    
    # ================================================================
    # STEP 5: Compare Original vs Replay
    # ================================================================
    
    print("─" * 60)
    print("STEP 5: COMPARE Original vs Replay")
    print("─" * 60)
    print()
    
    comparison = grid.compare(decision_id, replay_id)
    
    print("  ORIGINAL (support_v1):")
    original_resp = comparison['original_output'].get('response', 'N/A')
    print(f"    \"{original_resp[:60]}...\"")
    print()
    
    print("  REPLAY (support_v2):")
    replay_resp = comparison['replay_output'].get('response', 'N/A') if comparison['replay_output'] else 'N/A'
    print(f"    \"{replay_resp[:60]}...\"")
    print()
    
    print(f"  Output Changed: {comparison['output_changed']}")
    print()
    
    # ================================================================
    # STEP 6: Attach Human Correction
    # ================================================================
    
    print("─" * 60)
    print("STEP 6: Attach HUMAN CORRECTION")
    print("─" * 60)
    print()
    
    corrected = grid.attach_correction(
        decision_id=decision_id,
        correction={
            "response": "I apologize for the inconvenience. I can see you were charged "
                       "twice on your last billing cycle. I've initiated a refund of $XX.XX "
                       "which will appear in 3-5 business days. Is there anything else?"
        },
        corrected_by="senior_agent_jane",
        notes="Standard response for duplicate charge scenarios"
    )
    
    print(f"  ✓ Correction attached!")
    print(f"  Status: {corrected['status']}")
    print(f"  Corrected by: {corrected['correction']['corrected_by']}")
    print()
    
    # ================================================================
    # Summary
    # ================================================================
    
    print("=" * 60)
    print("  DEMO COMPLETE")
    print("=" * 60)
    print()
    print("  What happened:")
    print("  1. Recorded AI decision that missed billing issue")
    print("  2. Viewed decision in immutable ledger")
    print("  3. Marked as incorrect (for review)")
    print("  4. Created replay with improved prompt")
    print("  5. Compared outputs - saw improvement")
    print("  6. Attached human correction as ground truth")
    print()
    print(f"  Decision ID: {decision_id}")
    print(f"  Replay ID:   {replay_id}")
    print()
    print("  View in API: http://localhost:8000/docs")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
