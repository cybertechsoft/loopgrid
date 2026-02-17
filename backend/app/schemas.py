"""
LoopGrid API Schemas (Pydantic Models)
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime


# ================================================================
# Decision Schemas
# ================================================================

class DecisionCreate(BaseModel):
    """Schema for creating a new decision."""
    service_name: str = Field(..., description="Name of the service making the decision")
    decision_type: str = Field(..., description="Type of decision")
    input: Dict[str, Any] = Field(..., description="Input that triggered the decision")
    model: Dict[str, Any] = Field(..., description="Model info (provider, name, version)")
    output: Dict[str, Any] = Field(..., description="The AI's output")
    prompt: Optional[Dict[str, Any]] = Field(None, description="Prompt template and variables")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool/function calls made")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "service_name": "support-agent",
                "decision_type": "customer_support_reply",
                "input": {"message": "I was charged twice"},
                "model": {"provider": "openai", "name": "gpt-4", "version": "2024-01"},
                "prompt": {"template": "support_v1"},
                "output": {"response": "Your account looks fine."}
            }]
        }
    }


class DecisionResponse(BaseModel):
    """Schema for decision response."""
    decision_id: str
    created_at: datetime
    service_name: str
    decision_type: str
    input: Dict[str, Any]
    model: Dict[str, Any]
    output: Dict[str, Any]
    status: str
    content_hash: Optional[str] = None
    chain_hash: Optional[str] = None
    prompt: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    incorrect_reason: Optional[str] = None
    incorrect_at: Optional[datetime] = None
    correction: Optional[Dict[str, Any]] = None


class MarkIncorrectRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for marking incorrect")


class AttachCorrectionRequest(BaseModel):
    correction: Dict[str, Any] = Field(..., description="The corrected output")
    corrected_by: str = Field(..., description="Identifier of who made the correction")
    notes: Optional[str] = Field(None, description="Optional notes about the correction")


class DecisionListResponse(BaseModel):
    decisions: List[DecisionResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ================================================================
# Replay Schemas
# ================================================================

class ReplayCreate(BaseModel):
    decision_id: str = Field(..., description="ID of the decision to replay")
    overrides: Optional[Dict[str, Any]] = Field(None, description="Overrides for prompt, model, or input")
    triggered_by: str = Field("sdk", description="Who triggered the replay")


class ReplayResponse(BaseModel):
    replay_id: str
    decision_id: str
    created_at: datetime
    triggered_by: str
    overrides: Optional[Dict[str, Any]] = None
    replay_output: Optional[Dict[str, Any]] = None
    execution_status: str
    execution_mode: Optional[str] = None
    output_changed: bool
    diff_summary: Optional[str] = None


class CompareResponse(BaseModel):
    decision_id: str
    replay_id: str
    original_output: Dict[str, Any]
    replay_output: Optional[Dict[str, Any]]
    output_changed: bool
    diff_summary: Optional[str] = None