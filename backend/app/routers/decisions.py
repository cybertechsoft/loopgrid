"""
LoopGrid Decisions API Router
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import json

from ..database import get_db
from ..models import Decision, Replay
from ..schemas import (
    DecisionCreate,
    DecisionResponse,
    DecisionListResponse,
    MarkIncorrectRequest,
    AttachCorrectionRequest,
    CompareResponse
)

router = APIRouter()


@router.post("/decisions", response_model=DecisionResponse)
def record_decision(
    request: DecisionCreate,
    db: Session = Depends(get_db)
):
    """
    Record an AI decision to the ledger.
    
    This is the core operation. Every AI decision should be recorded
    for traceability and replay capability.
    """
    decision = Decision(
        service_name=request.service_name,
        decision_type=request.decision_type,
        input_data=json.dumps(request.input),
        model_data=json.dumps(request.model),
        output_data=json.dumps(request.output),
        prompt_data=json.dumps(request.prompt) if request.prompt else None,
        tool_calls_data=json.dumps(request.tool_calls) if request.tool_calls else None,
        metadata_data=json.dumps(request.metadata) if request.metadata else None
    )
    
    db.add(decision)
    db.commit()
    db.refresh(decision)
    
    return decision.to_dict()


@router.get("/decisions/{decision_id}", response_model=DecisionResponse)
def get_decision(
    decision_id: str,
    db: Session = Depends(get_db)
):
    """Get a decision by ID."""
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    
    if not decision:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    
    return decision.to_dict()


@router.get("/decisions", response_model=DecisionListResponse)
def list_decisions(
    service_name: Optional[str] = Query(None),
    decision_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List decisions with optional filters."""
    query = db.query(Decision)
    
    if service_name:
        query = query.filter(Decision.service_name == service_name)
    if decision_type:
        query = query.filter(Decision.decision_type == decision_type)
    if status:
        query = query.filter(Decision.status == status)
    
    total = query.count()
    
    decisions = query.order_by(Decision.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    return {
        "decisions": [d.to_dict() for d in decisions],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total
    }


@router.post("/decisions/{decision_id}/incorrect", response_model=DecisionResponse)
def mark_incorrect(
    decision_id: str,
    request: MarkIncorrectRequest = None,
    db: Session = Depends(get_db)
):
    """
    Mark a decision as incorrect.
    
    Flags the decision for review. Original data remains unchanged.
    """
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    
    if not decision:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    
    decision.status = "incorrect"
    decision.incorrect_at = datetime.utcnow()
    
    if request and request.reason:
        decision.incorrect_reason = request.reason
    
    db.commit()
    db.refresh(decision)
    
    return decision.to_dict()


@router.post("/decisions/{decision_id}/correction", response_model=DecisionResponse)
def attach_correction(
    decision_id: str,
    request: AttachCorrectionRequest,
    db: Session = Depends(get_db)
):
    """
    Attach a human correction to a decision.
    
    Human corrections become immutable ground truth for learning.
    """
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    
    if not decision:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    
    decision.status = "corrected"
    decision.correction_data = json.dumps(request.correction)
    decision.corrected_by = request.corrected_by
    decision.corrected_at = datetime.utcnow()
    
    if request.notes:
        decision.correction_notes = request.notes
    
    db.commit()
    db.refresh(decision)
    
    return decision.to_dict()


@router.get("/decisions/{decision_id}/compare/{replay_id}", response_model=CompareResponse)
def compare_decision_replay(
    decision_id: str,
    replay_id: str,
    db: Session = Depends(get_db)
):
    """Compare a decision with a replay."""
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    
    replay = db.query(Replay).filter(Replay.id == replay_id).first()
    if not replay:
        raise HTTPException(status_code=404, detail=f"Replay {replay_id} not found")
    
    if replay.decision_id != decision_id:
        raise HTTPException(
            status_code=400,
            detail=f"Replay {replay_id} is not for decision {decision_id}"
        )
    
    return {
        "decision_id": decision_id,
        "replay_id": replay_id,
        "original_output": decision.output,
        "replay_output": replay.replay_output,
        "output_changed": replay.output_changed,
        "diff_summary": replay.diff_summary
    }
