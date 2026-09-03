"""Minimal v0.8 SDK example. Requires a running LoopGrid server and service API key."""
import os, sys
from pathlib import Path

# When running from a source checkout, use the bundled SDK without installing it.
sdk = Path(__file__).resolve().parents[1] / "sdk" / "python"
if str(sdk) not in sys.path: sys.path.insert(0, str(sdk))
from loopgrid import LoopGrid

lg = LoopGrid(api_key=os.environ["LOOPGRID_SERVICE_KEY"])
d = lg.record_decision(
    decision_type="account_change",
    service_name="example-agent",
    privacy_mode="proof_only",
    agent={"id":"example-agent","version":"1.0"},
    authority={"acting_for":"Example Co","scope":["account:update"]},
    model={"provider":"example","name":"agent-model"},
    context={"prompt_version":"example-v1"},
    proposed_action={"tool":"crm.account.update"},
)
print("decision:", d["decision_id"])
print("workspace integrity:", lg.verify_workspace()["valid"])
