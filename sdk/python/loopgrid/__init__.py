"""
LoopGrid - Control Plane for AI Decision Reliability
=====================================================

A system of record for AI decisions. Capture every decision immutably,
replay failures with controlled overrides, and build ground truth from
human corrections.

Quick Start:
    from loopgrid import LoopGrid
    
    grid = LoopGrid(service_name="my-agent")
    
    decision = grid.record_decision(
        decision_type="support_reply",
        input={"message": "Help me"},
        model={"provider": "openai", "name": "gpt-4"},
        output={"response": "Sure!"}
    )

Documentation: https://github.com/cybertech/loopgrid
"""

from .client import LoopGrid, LoopGridError, LoopGridAPIError, __version__

__all__ = [
    "LoopGrid",
    "LoopGridError", 
    "LoopGridAPIError",
    "__version__"
]
