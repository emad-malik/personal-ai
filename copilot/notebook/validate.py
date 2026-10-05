"""Notebook validation using nbclient.

Stage 2: execute generated notebooks to verify they run without errors.
"""

from __future__ import annotations


def validate_notebook(path: str) -> dict:
    """Execute a notebook and return {ok: bool, errors: list[str]}."""
    raise NotImplementedError("Stage 2")
