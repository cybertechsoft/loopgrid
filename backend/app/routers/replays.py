"""
LoopGrid Replays API Router
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from ..database import get_db
from ..models import Decision, Replay
from ..schemas import ReplayCreate, ReplayResponse

router = APIRouter()


def simulate_replay(decision: Decision, overrides: dict = None) -> dict:
    """
    Simulate a replay execution.
    
    In V2, this will make actual AI API calls.
    For V1, we use pattern-based simulation.
    """
    original_output = decision.output
    
    # Check if we have overrides that might change behavior
    if overrides and "prompt" in overrides:
        prompt_template = overrides.get("prompt", {}).get("template", "")
        
        # Simulate improved output for v2 prompts
        if "v2" in prompt_template or "improved" in prompt_template:
            original_response = original_output.get("response", "")
            
            # Check for billing-related keywords
            input_text = str(decision.input).lower()
            if any(word in input_text for word in ["charged twice", "double charge", "duplicate", "billing"]):
                return {
                    "response": "I can see there's a duplicate charge on your account. "
                               "I've initiated a refund which will appear in 3-5 business days. "
                               "Is there anything else I can help with?"
                }
            
            # Generic improvement
            return {
                "response": f"[Improved with {prompt_template}] {original_response}"
            }
    
    # No changes - return original
    return original_output


@router.post("/replays", response_model=ReplayResponse)
def create_replay(
    request: ReplayCreate,
    db: Session = Depends(get_db)
):
    """
    Create a replay for a decision.
    
    A replay is a forked execution with optional overrides.
    Use to test different prompts, models, or inputs.
    """
    # Get the original decision
    decision = db.query(Decision).filter(Decision.id == request.decision_id).first()
    
    if not decision:
        raise HTTPException(
            status_code=404,
            detail=f"Decision {request.decision_id} not found"
        )
    
    # Execute replay (simulated in V1)
    replay_output = simulate_replay(decision, request.overrides)
    
    # Compare outputs
    original_output = decision.output
    output_changed = replay_output != original_output
    
    # Generate diff summary
    diff_summary = None
    if output_changed:
        diff_summary = "Output changed after replay with overrides"
    
    # Create replay record
    replay = Replay(
        decision_id=request.decision_id,
        overrides_data=json.dumps(request.overrides) if request.overrides else None,
        triggered_by=request.triggered_by,
        replay_output_data=json.dumps(replay_output),
        execution_status="completed",
        output_changed=output_changed,
        diff_summary=diff_summary
    )
    
    db.add(replay)
    db.commit()
    db.refresh(replay)
    
    return replay.to_dict()


@router.get("/replays/{replay_id}", response_model=ReplayResponse)
def get_replay(
    replay_id: str,
    db: Session = Depends(get_db)
):
    """Get a replay by ID."""
    replay = db.query(Replay).filter(Replay.id == replay_id).first()
    
    if not replay:
        raise HTTPException(status_code=404, detail=f"Replay {replay_id} not found")
    
    return replay.to_dict()
