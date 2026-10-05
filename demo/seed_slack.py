"""Seed a demo Slack workspace with synthetic messages from seed_messages.json.

Usage:
    python demo/seed_slack.py

Requires SLACK_BOT_TOKEN and SLACK_CHANNEL_ID in .env.
"""

from __future__ import annotations


def seed() -> None:
    """Post seed messages into the demo Slack channel."""
    raise NotImplementedError("Stage 1 -- set up demo workspace first")


if __name__ == "__main__":
    seed()
