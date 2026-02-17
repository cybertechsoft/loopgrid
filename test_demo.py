#!/usr/bin/env python3
"""
LoopGrid Demo — Complete workflow including hash chain and compliance.

Prerequisites:
    1. Start the server: python run_server.py
    2. Run this demo: python test_demo.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sdk', 'python'))

from loopgrid import LoopGrid, LoopGridError


def main():
    print()
    print("=" * 60)
    print("  LoopGrid Demo")
    print("  Control Plane for AI Decision Reliability")
    print("=" * 60)
    print()
    
    grid = LoopGrid(base_url="http://localhost:8000", service_name="support-agent")
    
    try:
        health = grid.health()
        print(f"✓ Connected to LoopGrid ({health.get('version', 'unknown')})")
    except LoopGridError as e:
        print(f"✗ Cannot connect: {e}")
        print("\n  Start the server first: python run_server.py")
        return 1
    
    print()
    
    # STEP 1: Record Decision
    print("─" * 60)
    print("STEP 1: Record AI Decision (with cryptographic hash)")
    print("─" * 60)
    print()
    
    decision = grid.record_decision(
        decision_type="customer_support_reply",
        input={"message": "I was charged twice for my subscription", "customer_id": "cust_123"},
        model={"provider": "openai", "name": "gpt-4", "version": "2024-01"},
        prompt={"template": "support_v1", "text": "You are a helpful support agent."},
        output={"response": "Your account looks fine to me. Is there anything else I can help with?"},
        metadata={"latency_ms": 1240, "tokens": 150}
    )
    
    decision_id = decision["decision_id"]
    print(f"  ✓ Decision recorded: {decision_id}")
    print(f"    Content hash: {decision['content_hash'][:16]}...")
    print(f"    Chain hash:   {decision['chain_hash'][:16]}...")
    print()
    
    # STEP 2: Verify Integrity
    print("─" * 60)
    print("STEP 2: Verify Ledger Integrity (hash chain)")
    print("─" * 60)
    print()
    
    integrity = grid.verify_integrity()
    print(f"  ✓ Chain valid: {integrity['integrity']['valid']}")
    print(f"    {integrity['integrity']['message']}")
    print()
    
    # STEP 3: Mark Incorrect
    print("─" * 60)
    print("STEP 3: Mark Decision as INCORRECT")
    print("─" * 60)
    print()
    
    updated = grid.mark_incorrect(decision_id, reason="AI missed the duplicate charge")
    print(f"  ✓ Status: {updated['status']}")
    print()
    
    # STEP 4: Replay
    print("─" * 60)
    print("STEP 4: Create REPLAY with Improved Prompt")
    print("─" * 60)
    print()
    
    replay = grid.create_replay(
        decision_id=decision_id,
        overrides={"prompt": {"template": "support_v2", "text": "Always check for billing issues first."}},
        triggered_by="human_review"
    )
    
    replay_id = replay["replay_id"]
    print(f"  ✓ Replay: {replay_id}")
    print(f"    Mode: {replay.get('execution_mode', 'unknown')}")
    print(f"    Output changed: {replay['output_changed']}")
    print()
    
    # STEP 5: Compare
    print("─" * 60)
    print("STEP 5: COMPARE Original vs Replay")
    print("─" * 60)
    print()
    
    comparison = grid.compare(decision_id, replay_id)
    orig = comparison['original_output'].get('response', 'N/A')[:60]
    rep = comparison['replay_output'].get('response', 'N/A')[:60] if comparison['replay_output'] else 'N/A'
    print(f"  ORIGINAL: \"{orig}...\"")
    print(f"  REPLAY:   \"{rep}...\"")
    print(f"  Changed:  {comparison['output_changed']}")
    print()
    
    # STEP 6: Human Correction
    print("─" * 60)
    print("STEP 6: Attach HUMAN CORRECTION")
    print("─" * 60)
    print()
    
    corrected = grid.attach_correction(
        decision_id=decision_id,
        correction={"response": "I see you were charged twice. Refund of $XX.XX initiated — 3-5 business days."},
        corrected_by="senior_agent_jane",
        notes="Standard duplicate charge response"
    )
    print(f"  ✓ Status: {corrected['status']}")
    print()
    
    # STEP 7: Compliance Report
    print("─" * 60)
    print("STEP 7: Generate COMPLIANCE REPORT")
    print("─" * 60)
    print()
    
    report = grid.compliance_report()
    art12 = report["eu_ai_act_mapping"]["article_12_record_keeping"]["status"]
    art14 = report["eu_ai_act_mapping"]["article_14_human_oversight"]["status"]
    print(f"  EU AI Act Article 12 (Record-Keeping): {art12.upper()}")
    print(f"  EU AI Act Article 14 (Human Oversight): {art14.upper()}")
    print(f"  Ledger integrity: {'PASS' if report['ledger_integrity']['valid'] else 'FAIL'}")
    print()
    
    # Summary
    print("=" * 60)
    print("  DEMO COMPLETE")
    print("=" * 60)
    print()
    print("  What happened:")
    print("  1. Recorded decision with cryptographic hash chain")
    print("  2. Verified ledger integrity (tamper-proof)")
    print("  3. Marked as incorrect for review")
    print("  4. Created replay with improved prompt")
    print("  5. Compared outputs side-by-side")
    print("  6. Attached human correction as ground truth")
    print("  7. Generated EU AI Act compliance report")
    print()
    print(f"  Decision: {decision_id}")
    print(f"  Replay:   {replay_id}")
    print()
    print("  API Docs: http://localhost:8000/docs")
    print("  HTML Compliance Report: http://localhost:8000/v1/compliance/report/html")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
