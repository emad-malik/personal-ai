"""Read messages from a Slack channel and extract content decisions.

Stage 1: fetch channel history, parse into structured messages.
"""

from __future__ import annotations


def fetch_channel_history(channel_id: str, limit: int = 100) -> list[dict]:
    """Fetch recent messages from a Slack channel."""
    raise NotImplementedError("Stage 1")


def extract_decisions(messages: list[dict]) -> list[dict]:
    """Use LLM to extract content decisions and deadlines from messages."""
    raise NotImplementedError("Stage 1")
