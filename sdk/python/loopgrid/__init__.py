"""
LoopGrid - Control Plane for AI Decision Reliability
=====================================================

Quick Start:
    from loopgrid import LoopGrid
    
    grid = LoopGrid(service_name="my-agent")
    decision = grid.record_decision(
        decision_type="support_reply",
        input={"message": "Help me"},
        model={"provider": "openai", "name": "gpt-4"},
        output={"response": "Sure!"}
    )

Documentation: https://github.com/cybertechsoft/loopgrid
"""

from .client import LoopGrid, LoopGridError, LoopGridAPIError, __version__

__all__ = ["LoopGrid", "LoopGridError", "LoopGridAPIError", "__version__"]
