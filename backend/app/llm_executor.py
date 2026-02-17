"""
LoopGrid LLM Executor
=====================

Executes real LLM API calls for the Replay Engine.
Supports OpenAI and Anthropic. Falls back to simulation
if no API keys are configured.
"""

import time
import json
from typing import Dict, Any, Optional, Tuple

from .config import settings


def _call_openai(model_name: str, prompt_text: str, input_data: dict, timeout: int) -> Tuple[dict, int, int]:
    """Call OpenAI API. Returns (output, latency_ms, tokens)."""
    import openai
    
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    messages = []
    if prompt_text:
        messages.append({"role": "system", "content": prompt_text})
    
    # Build user message from input
    user_msg = input_data.get("message") or json.dumps(input_data)
    messages.append({"role": "user", "content": str(user_msg)})
    
    start = time.time()
    response = client.chat.completions.create(
        model=model_name or "gpt-4",
        messages=messages,
        timeout=timeout
    )
    latency_ms = int((time.time() - start) * 1000)
    
    output_text = response.choices[0].message.content
    tokens = response.usage.total_tokens if response.usage else 0
    
    return {"response": output_text}, latency_ms, tokens


def _call_anthropic(model_name: str, prompt_text: str, input_data: dict, timeout: int) -> Tuple[dict, int, int]:
    """Call Anthropic API. Returns (output, latency_ms, tokens)."""
    import anthropic
    
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    user_msg = input_data.get("message") or json.dumps(input_data)
    
    start = time.time()
    response = client.messages.create(
        model=model_name or "claude-sonnet-4-20250514",
        max_tokens=1024,
        system=prompt_text or "You are a helpful assistant.",
        messages=[{"role": "user", "content": str(user_msg)}]
    )
    latency_ms = int((time.time() - start) * 1000)
    
    output_text = response.content[0].text
    tokens = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
    
    return {"response": output_text}, latency_ms, tokens


def _simulate_replay(original_output: dict, overrides: Optional[dict], input_data: dict) -> Tuple[dict, int, int, str]:
    """
    Fallback simulation when no API keys are configured.
    Returns (output, latency_ms, tokens, note).
    """
    if overrides and "prompt" in overrides:
        prompt_template = overrides.get("prompt", {}).get("template", "")
        
        if "v2" in prompt_template or "improved" in prompt_template:
            input_text = str(input_data).lower()
            if any(word in input_text for word in ["charged twice", "double charge", "duplicate", "billing"]):
                return (
                    {"response": "I can see there's a duplicate charge on your account. I've initiated a refund which will appear in 3-5 business days. Is there anything else I can help with?"},
                    150, 0, "simulated"
                )
            return (
                {"response": f"[Improved with {prompt_template}] {original_output.get('response', '')}"},
                100, 0, "simulated"
            )
    
    return original_output, 0, 0, "simulated"


def execute_replay(
    original_input: dict,
    original_model: dict,
    original_prompt: Optional[dict],
    original_output: dict,
    overrides: Optional[dict] = None
) -> dict:
    """
    Execute a replay — either live LLM call or simulation.
    
    Args:
        original_input: The original decision's input
        original_model: The original model info
        original_prompt: The original prompt info
        original_output: The original output (for simulation fallback)
        overrides: Optional overrides for prompt, model, input
    
    Returns:
        {
            "output": {...},
            "execution_mode": "live" | "simulated",
            "latency_ms": int,
            "tokens": int,
            "provider": str
        }
    """
    # Apply overrides
    effective_input = overrides.get("input", original_input) if overrides else original_input
    effective_model = {**(original_model or {}), **(overrides.get("model", {}) if overrides else {})}
    effective_prompt = {**(original_prompt or {}), **(overrides.get("prompt", {}) if overrides else {})}
    
    provider = effective_model.get("provider", "").lower()
    model_name = effective_model.get("name", "")
    prompt_text = effective_prompt.get("text", effective_prompt.get("template", ""))
    
    # Try live execution
    try:
        if provider == "openai" and settings.has_openai():
            output, latency_ms, tokens = _call_openai(
                model_name, prompt_text, effective_input, settings.REPLAY_TIMEOUT
            )
            return {
                "output": output, "execution_mode": "live",
                "latency_ms": latency_ms, "tokens": tokens, "provider": "openai"
            }
        
        if provider in ("anthropic", "claude") and settings.has_anthropic():
            output, latency_ms, tokens = _call_anthropic(
                model_name, prompt_text, effective_input, settings.REPLAY_TIMEOUT
            )
            return {
                "output": output, "execution_mode": "live",
                "latency_ms": latency_ms, "tokens": tokens, "provider": "anthropic"
            }
    except ImportError:
        pass  # SDK not installed, fall through to simulation
    except Exception as e:
        # API error — return error info but don't crash
        return {
            "output": original_output, "execution_mode": "error",
            "latency_ms": 0, "tokens": 0, "provider": provider,
            "error": str(e)
        }
    
    # Fallback: simulation
    output, latency_ms, tokens, mode = _simulate_replay(original_output, overrides, effective_input)
    return {
        "output": output, "execution_mode": mode,
        "latency_ms": latency_ms, "tokens": tokens, "provider": "simulation"
    }
