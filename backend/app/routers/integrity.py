"""
LoopGrid Integrity Verification Router
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import Decision
from ..hashing import verify_chain

router = APIRouter()


@router.get("/integrity/verify")
def verify_ledger_integrity(
    service_name: Optional[str] = Query(None, description="Verify only a specific service"),
    db: Session = Depends(get_db)
):
    """
    Verify the hash chain integrity of the decision ledger.
    
    Walks the entire chain and confirms no records have been
    tampered with, inserted, or deleted.
    """
    query = db.query(Decision).order_by(Decision.created_at.asc())
    
    if service_name:
        query = query.filter(Decision.service_name == service_name)
    
    decisions = query.all()
    result = verify_chain(decisions)
    
    return {
        "integrity": result,
        "service_filter": service_name
    }
