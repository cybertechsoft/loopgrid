"""Tests for cryptographic hashing functions."""

from backend.app.hashing import compute_content_hash, compute_chain_hash


def test_content_hash_deterministic():
    """Same input always produces same hash."""
    data = {"service_name": "test", "decision_type": "reply", "input": {"msg": "hi"},
            "model": {"provider": "openai", "name": "gpt-4"}, "output": {"response": "hello"},
            "prompt": None, "tool_calls": None, "metadata": None}
    h1 = compute_content_hash(data)
    h2 = compute_content_hash(data)
    assert h1 == h2
    assert len(h1) == 64


def test_content_hash_changes_with_data():
    """Different content produces different hash."""
    base = {"service_name": "test", "decision_type": "reply", "input": {"msg": "hi"},
            "model": {"provider": "openai", "name": "gpt-4"}, "output": {"response": "hello"},
            "prompt": None, "tool_calls": None, "metadata": None}
    modified = {**base, "output": {"response": "goodbye"}}
    assert compute_content_hash(base) != compute_content_hash(modified)


def test_chain_hash_genesis():
    """First decision chains from GENESIS."""
    h1 = compute_chain_hash("abc123", None)
    h2 = compute_chain_hash("abc123", None)
    assert h1 == h2
    assert len(h1) == 64


def test_chain_hash_links():
    """Chain hash changes when previous hash changes."""
    h1 = compute_chain_hash("abc123", "prev_hash_1")
    h2 = compute_chain_hash("abc123", "prev_hash_2")
    assert h1 != h2


def test_chain_hash_content_sensitive():
    """Chain hash changes when content hash changes."""
    h1 = compute_chain_hash("content_1", "same_prev")
    h2 = compute_chain_hash("content_2", "same_prev")
    assert h1 != h2
