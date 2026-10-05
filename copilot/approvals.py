"""Human-in-the-loop approval for outbound Slack messages.

Stage 2: present draft messages for user approval before sending.
"""

from __future__ import annotations


def request_approval(draft: str, channel_id: str) -> bool:
    """Show draft to user and wait for approval. Returns True if approved."""
    raise NotImplementedError("Stage 2")
