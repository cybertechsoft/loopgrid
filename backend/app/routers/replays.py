"""
LoopGrid Replays API Router
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from ..database import get_db
from ..models import Decision, Replay
from ..llm_executor import execute_replay
from ..schemas import ReplayCreate, ReplayResponse

router = APIRouter()


@router.post("/replays", response_model=ReplayResponse)
def create_replay(
    request: ReplayCreate,
    db: Session = Depends(get_db)
):
    """
    Create a replay for a decision.
    
    Uses real LLM API calls if API keys are configured,
    otherwise falls back to simulation mode.
    """
    decision = db.query(Decision).filter(Decision.id == request.decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail=f"Decision {request.decision_id} not found")
    
    # Execute replay (live LLM or simulation)
    result = execute_replay(
        original_input=decision.input,
        original_model=decision.model,
        original_prompt=decision.prompt,
        original_output=decision.output,
        overrides=request.overrides
    )
    
    replay_output = result["output"]
    original_output = decision.output
    output_changed = replay_output != original_output
    
    diff_summary = None
    if output_changed:
        mode = result["execution_mode"]
        diff_summary = f"Output changed after replay ({mode} execution)"
    
    replay = Replay(
        decision_id=request.decision_id,
        overrides_data=json.dumps(request.overrides) if request.overrides else None,
        triggered_by=request.triggered_by,
        replay_output_data=json.dumps(replay_output),
        execution_status="completed" if result["execution_mode"] != "error" else "failed",
        execution_mode=result["execution_mode"],
        execution_latency_ms=str(result.get("latency_ms", 0)),
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
