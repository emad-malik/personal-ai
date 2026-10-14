"""Upload a file to Slack as a native attachment.

Why this exists: the Hermes gateway uploads files it finds in replies, but it
skips source-style extensions such as .ipynb (tested Oct 14). This sends the
notebook straight through the Slack API instead.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _default_user() -> str:
    allowed = [u.strip() for u in os.getenv("SLACK_ALLOWED_USERS", "").split(",") if u.strip()]
    if not allowed:
        raise RuntimeError("Pass --user/--channel, or set SLACK_ALLOWED_USERS in .env")
    return allowed[0]


def upload_file(path: str, *, user_id: str | None = None, channel: str | None = None,
                comment: str | None = None, client=None) -> str:
    """Upload path to a channel, or to a DM with user_id. Returns the file permalink."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if client is None:
        from slack_sdk import WebClient

        token = os.getenv("SLACK_BOT_TOKEN")
        if not token:
            raise RuntimeError("SLACK_BOT_TOKEN is not set")
        client = WebClient(token=token)
    if channel is None:
        channel = client.conversations_open(users=user_id or _default_user())["channel"]["id"]
    resp = client.files_upload_v2(
        channel=channel,
        file=path,
        title=os.path.basename(path),
        initial_comment=comment,
    )
    f = resp.get("file") or (resp.get("files") or [{}])[0]
    return f.get("permalink", "")
