"""Persistent memory store using ChromaDB.

Stage 1: store and retrieve content decisions, deadlines, context.
"""

from __future__ import annotations


def store_decision(decision: dict) -> None:
    """Persist a content decision to ChromaDB."""
    raise NotImplementedError("Stage 1")


def query_context(query: str, top_k: int = 5) -> list[dict]:
    """Retrieve relevant past decisions and context."""
    raise NotImplementedError("Stage 1")
