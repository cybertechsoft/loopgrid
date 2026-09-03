"""Consequential refund lifecycle: decision -> policy -> human approval -> action -> outcome."""
import os, sys
from pathlib import Path
sdk = Path(__file__).resolve().parents[1] / "sdk" / "python"
if str(sdk) not in sys.path: sys.path.insert(0, str(sdk))
from loopgrid import LoopGrid

lg=LoopGrid(api_key=os.environ["LOOPGRID_SERVICE_KEY"])
d=lg.record_decision(
    decision_type="customer_refund", service_name="support-agent",
    agent={"id":"support-agent","version":"1.0"},
    authority={"acting_for":"Example Support","limit_usd":1500,"scope":["refund:create"]},
    model={"provider":"openai","name":"example-model"},
    context={"prompt_version":"support-v1","retrieval_refs":["refund-policy"]},
    input={"message":"Duplicate charge reported"},
    proposed_action={"tool":"stripe.refunds.create","amount":1000,"currency":"USD"},
)
did=d["decision_id"]
lg.model_completed(did,{"response":"Duplicate charge detected; propose $1,000 refund."},actor_id="support-agent")
policy=lg.evaluate_policy("refund-policy",{"amount":1000},{"limit_usd":1500})
lg.policy_evaluated(did,policy,actor_id="refund-policy")
lg.human_approved(did,"reviewer@example.com","Duplicate charge verified")
lg.tool_executed(did,{"tool":"stripe.refunds.create","external_reference":"re_example"},actor_id="stripe")
lg.outcome_observed(did,{"status":"succeeded","external_reference":"re_example"})
record=lg.get_decision(did)
print("decision:",did)
print("evidence coverage:",record["coverage"]["score"])
print("verification:",record["verification"]["valid"])
lg.save_evidence(did,Path(f"{did}-evidence.zip"),include_payloads=False)
print("saved:",f"{did}-evidence.zip")
