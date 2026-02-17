"""
LoopGrid Database Models
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import json

from .database import Base


def generate_decision_id():
    return f"dec_{uuid.uuid4().hex[:12]}"


def generate_replay_id():
    return f"rep_{uuid.uuid4().hex[:12]}"


class Decision(Base):
    """
    Immutable record of an AI decision.
    
    Once recorded, decisions cannot be modified.
    Each decision is cryptographically hashed and chained
    to the previous decision for tamper-evidence.
    """
    __tablename__ = "decisions"
    
    id = Column(String, primary_key=True, default=generate_decision_id)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Attribution
    service_name = Column(String, nullable=False, index=True)
    decision_type = Column(String, nullable=False, index=True)
    
    # Decision data (stored as JSON strings)
    input_data = Column(Text, nullable=False)
    model_data = Column(Text, nullable=False)
    prompt_data = Column(Text, nullable=True)
    tool_calls_data = Column(Text, nullable=True)
    output_data = Column(Text, nullable=False)
    metadata_data = Column(Text, nullable=True)
    
    # Hash chain (GAP #1 fix — cryptographic immutability)
    content_hash = Column(String(64), nullable=True, index=True)
    chain_hash = Column(String(64), nullable=True, index=True)
    
    # Status
    status = Column(String, default="recorded", index=True)
    incorrect_reason = Column(Text, nullable=True)
    incorrect_at = Column(DateTime, nullable=True)
    
    # Human correction
    correction_data = Column(Text, nullable=True)
    corrected_by = Column(String, nullable=True)
    corrected_at = Column(DateTime, nullable=True)
    correction_notes = Column(Text, nullable=True)
    
    # Relationships
    replays = relationship("Replay", back_populates="decision")
    
    @property
    def input(self):
        return json.loads(self.input_data) if self.input_data else {}
    
    @property
    def model(self):
        return json.loads(self.model_data) if self.model_data else {}
    
    @property
    def prompt(self):
        return json.loads(self.prompt_data) if self.prompt_data else None
    
    @property
    def tool_calls(self):
        return json.loads(self.tool_calls_data) if self.tool_calls_data else None
    
    @property
    def output(self):
        return json.loads(self.output_data) if self.output_data else {}
    
    @property
    def meta(self):
        return json.loads(self.metadata_data) if self.metadata_data else None
    
    @property
    def correction(self):
        return json.loads(self.correction_data) if self.correction_data else None
    
    def to_dict(self):
        result = {
            "decision_id": self.id,
            "created_at": self.created_at.isoformat(),
            "service_name": self.service_name,
            "decision_type": self.decision_type,
            "input": self.input,
            "model": self.model,
            "output": self.output,
            "status": self.status,
            "content_hash": self.content_hash,
            "chain_hash": self.chain_hash
        }
        
        if self.prompt:
            result["prompt"] = self.prompt
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.meta:
            result["metadata"] = self.meta
        if self.incorrect_reason:
            result["incorrect_reason"] = self.incorrect_reason
            result["incorrect_at"] = self.incorrect_at.isoformat() if self.incorrect_at else None
        if self.correction:
            result["correction"] = {
                "output": self.correction,
                "corrected_by": self.corrected_by,
                "corrected_at": self.corrected_at.isoformat() if self.corrected_at else None,
                "notes": self.correction_notes
            }
        
        return result


class Replay(Base):
    """
    A forked execution of a past decision.
    Replays allow testing different prompts/models on the same input.
    """
    __tablename__ = "replays"
    
    id = Column(String, primary_key=True, default=generate_replay_id)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Link to original decision
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=False)
    decision = relationship("Decision", back_populates="replays")
    
    # Replay configuration
    overrides_data = Column(Text, nullable=True)
    triggered_by = Column(String, default="system")
    
    # Replay execution
    replay_output_data = Column(Text, nullable=True)
    execution_status = Column(String, default="completed")
    execution_mode = Column(String, default="simulated")  # "live", "simulated", "error"
    execution_latency_ms = Column(String, nullable=True)
    
    # Comparison
    output_changed = Column(Boolean, default=False)
    diff_summary = Column(Text, nullable=True)
    
    @property
    def overrides(self):
        return json.loads(self.overrides_data) if self.overrides_data else None
    
    @property
    def replay_output(self):
        return json.loads(self.replay_output_data) if self.replay_output_data else None
    
    def to_dict(self):
        return {
            "replay_id": self.id,
            "decision_id": self.decision_id,
            "created_at": self.created_at.isoformat(),
            "triggered_by": self.triggered_by,
            "overrides": self.overrides,
            "replay_output": self.replay_output,
            "execution_status": self.execution_status,
            "execution_mode": self.execution_mode,
            "output_changed": self.output_changed,
            "diff_summary": self.diff_summary
        }
