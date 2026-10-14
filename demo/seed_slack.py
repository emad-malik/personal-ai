"""Post the synthetic messages from seed_messages.json into the demo Slack channel.

Usage:
    python demo/seed_slack.py --dry-run
    python demo/seed_slack.py

Needs SLACK_BOT_TOKEN and SLACK_CHANNEL_ID in .env, the app invited to the
channel, and the chat:write.customize scope (posts under each pseudo name).
"""

from __future__ import annotations

import argparse
import json
import os
import time

from dotenv import load_dotenv

load_dotenv()

SEED = os.path.join(os.path.dirname(__file__), "seed_messages.json")


def seed(dry_run: bool = False) -> None:
    with open(SEED, encoding="utf-8") as f:
        messages = json.load(f)
    if dry_run:
        for m in messages:
            print(f"{m['ts']}  {m['user']}: {m['text'][:70]}")
        print(f"\n{len(messages)} messages (dry run, nothing posted)")
        return

    from slack_sdk import WebClient

    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    channel = os.environ["SLACK_CHANNEL_ID"]
    for m in messages:
        # Slack stamps messages with the current time, so the original date is kept
        # in the text prefix for the demo and in seed_messages.json for tests.
        client.chat_postMessage(
            channel=channel,
            username=m["user"],
            text=f"[{m['ts'][:10]}] {m['text']}",
        )
        time.sleep(1.1)  # stay under Slack's 1 message/second guidance
    print(f"Posted {len(messages)} messages")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    seed(p.parse_args().dry_run)
