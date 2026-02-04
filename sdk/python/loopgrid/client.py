"""
LoopGrid Python SDK
===================

The control plane for AI decision reliability.

Installation:
    pip install loopgrid

Usage:
    from loopgrid import LoopGrid
    
    grid = LoopGrid(service_name="my-agent")
    
    decision = grid.record_decision(
        decision_type="customer_support_reply",
        input={"message": "I was charged twice"},
        model={"provider": "openai", "name": "gpt-4"},
        output={"response": "Refund initiated."}
    )

Documentation: https://github.com/cybertech/loopgrid
"""

import requests
from typing import Dict, Any, Optional, List
from datetime import datetime


__version__ = "0.1.0"


class LoopGridError(Exception):
    """Base exception for LoopGrid SDK errors."""
    pass


class LoopGridAPIError(LoopGridError):
    """API error from LoopGrid server."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error {status_code}: {detail}")


class LoopGrid:
    """
    LoopGrid SDK Client
    
    The main interface for interacting with the LoopGrid control plane.
    
    Args:
        base_url: URL of the LoopGrid server (default: http://localhost:8000)
        service_name: Name of your service for decision attribution
        timeout: Request timeout in seconds (default: 30)
    
    Example:
        grid = LoopGrid(
            base_url="http://localhost:8000",
            service_name="support-agent"
        )
        
        decision = grid.record_decision(
            decision_type="customer_support_reply",
            input={"message": "Help me"},
            model={"provider": "openai", "name": "gpt-4"},
            output={"response": "Sure!"}
        )
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        service_name: str = "default",
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.timeout = timeout
        self._session = requests.Session()
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to LoopGrid API."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self._session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code >= 400:
                try:
                    error_detail = response.json().get("detail", response.text)
                except:
                    error_detail = response.text
                raise LoopGridAPIError(response.status_code, error_detail)
            
            return response.json()
            
        except requests.exceptions.ConnectionError:
            raise LoopGridError(
                f"Cannot connect to LoopGrid at {self.base_url}. "
                "Is the server running? Start with: python run_server.py"
            )
        except requests.exceptions.Timeout:
            raise LoopGridError(f"Request timed out after {self.timeout}s")
    
    # ================================================================
    # Decision Operations
    # ================================================================
    
    def record_decision(
        self,
        decision_type: str,
        input: Dict[str, Any],
        model: Dict[str, Any],
        output: Dict[str, Any],
        prompt: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """
        Record an AI decision to the ledger.
        
        This is the core operation. Every AI decision should be recorded
        for traceability and replay capability.
        
        Args:
            decision_type: Type of decision (e.g., "customer_support_reply")
            input: The input that triggered the decision
            model: Model info (provider, name, version)
            output: The AI's output
            prompt: Optional prompt info (template, variables)
            tool_calls: Optional tool/function calls made
            metadata: Optional additional metadata
        
        Returns:
            The recorded decision with unique decision_id
        
        Example:
            decision = grid.record_decision(
                decision_type="support_reply",
                input={"message": "I was charged twice"},
                model={"provider": "openai", "name": "gpt-4"},
                output={"response": "Refund initiated."}
            )
            print(decision["decision_id"])  # dec_abc123
        """
        data = {
            "service_name": self.service_name,
            "decision_type": decision_type,
            "input": input,
            "model": model,
            "output": output
        }
        
        if prompt:
            data["prompt"] = prompt
        if tool_calls:
            data["tool_calls"] = tool_calls
        if metadata:
            data["metadata"] = metadata
        
        return self._request("POST", "/v1/decisions", data=data)
    
    def get_decision(self, decision_id: str) -> Dict:
        """Get a decision by ID."""
        return self._request("GET", f"/v1/decisions/{decision_id}")
    
    def list_decisions(
        self,
        service_name: Optional[str] = None,
        decision_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict:
        """List decisions with optional filters."""
        params = {"page": page, "page_size": page_size}
        if service_name:
            params["service_name"] = service_name
        if decision_type:
            params["decision_type"] = decision_type
        if status:
            params["status"] = status
        
        return self._request("GET", "/v1/decisions", params=params)
    
    def mark_incorrect(
        self,
        decision_id: str,
        reason: Optional[str] = None
    ) -> Dict:
        """
        Mark a decision as incorrect.
        
        Flags the decision for review. Original data remains unchanged.
        
        Args:
            decision_id: The decision to mark
            reason: Optional reason for marking incorrect
        """
        data = {}
        if reason:
            data["reason"] = reason
        
        return self._request(
            "POST",
            f"/v1/decisions/{decision_id}/incorrect",
            data=data
        )
    
    def attach_correction(
        self,
        decision_id: str,
        correction: Dict[str, Any],
        corrected_by: str,
        notes: Optional[str] = None
    ) -> Dict:
        """
        Attach a human correction to a decision.
        
        Human corrections become immutable ground truth for learning.
        
        Args:
            decision_id: The decision to correct
            correction: The corrected output
            corrected_by: Identifier of who made the correction
            notes: Optional notes about the correction
        
        Example:
            grid.attach_correction(
                decision_id="dec_abc123",
                correction={"response": "I see the duplicate. Refund initiated."},
                corrected_by="agent_42"
            )
        """
        data = {
            "correction": correction,
            "corrected_by": corrected_by
        }
        if notes:
            data["notes"] = notes
        
        return self._request(
            "POST",
            f"/v1/decisions/{decision_id}/correction",
            data=data
        )
    
    # ================================================================
    # Replay Operations
    # ================================================================
    
    def create_replay(
        self,
        decision_id: str,
        overrides: Optional[Dict[str, Any]] = None,
        triggered_by: str = "sdk"
    ) -> Dict:
        """
        Create a replay for a decision.
        
        A replay is a forked execution with optional overrides.
        Use to test different prompts, models, or inputs.
        
        Args:
            decision_id: The decision to replay
            overrides: Optional overrides for prompt, model, or input
            triggered_by: Identifier of who triggered the replay
        
        Returns:
            The replay result including comparison
        
        Example:
            replay = grid.create_replay(
                decision_id="dec_abc123",
                overrides={"prompt": {"template": "support_v2"}}
            )
            print(replay["output_changed"])  # True
        """
        data = {
            "decision_id": decision_id,
            "triggered_by": triggered_by
        }
        if overrides:
            data["overrides"] = overrides
        
        return self._request("POST", "/v1/replays", data=data)
    
    def get_replay(self, replay_id: str) -> Dict:
        """Get a replay by ID."""
        return self._request("GET", f"/v1/replays/{replay_id}")
    
    def compare(self, decision_id: str, replay_id: str) -> Dict:
        """
        Compare a decision with a replay.
        
        Returns side-by-side comparison showing what changed.
        """
        return self._request(
            "GET",
            f"/v1/decisions/{decision_id}/compare/{replay_id}"
        )
    
    # ================================================================
    # Utility Methods
    # ================================================================
    
    def health(self) -> Dict:
        """Check if the LoopGrid server is healthy."""
        return self._request("GET", "/health")
    
    def __repr__(self):
        return f"LoopGrid(base_url='{self.base_url}', service_name='{self.service_name}')"
