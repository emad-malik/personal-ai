"""Smoke test for LLM client (requires NEBIUS_API_KEY)."""

from __future__ import annotations

import pytest
from copilot.llm import chat, NANO


@pytest.mark.skipif(
    not __import__("os").getenv("NEBIUS_API_KEY"),
    reason="NEBIUS_API_KEY not set",
)
def test_nano_responds():
    reply = chat("Say hello in exactly three words.", model=NANO, max_tokens=32)
    assert len(reply) > 0
