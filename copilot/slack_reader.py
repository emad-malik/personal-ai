"""Read a Slack channel (or the seed file) and extract memory items with Nano.

Stage 2: messages in, structured deadlines/decisions/feedback out.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from copilot import memory
from copilot.llm import NANO, chat

SEED_PATH = os.path.join("demo", "seed_messages.json")


def load_seed(path: str = SEED_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_channel_history(channel_id: str | None = None, limit: int = 500) -> list[dict]:
    """Fetch channel history from Slack, oldest first, as {user, text, ts} dicts."""
    from slack_sdk import WebClient

    token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = channel_id or os.getenv("SLACK_CHANNEL_ID")
    if not token or not channel_id:
        raise RuntimeError("SLACK_BOT_TOKEN and SLACK_CHANNEL_ID must be set in .env")
    client = WebClient(token=token)

    raw, cursor = [], None
    while len(raw) < limit:
        resp = client.conversations_history(channel=channel_id, cursor=cursor, limit=200)
        raw.extend(resp["messages"])
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break

    names: dict[str, str] = {}

    def who(m: dict) -> str:
        if m.get("username"):  # seeded messages carry a display-name override
            return m["username"]
        uid = m.get("user", "unknown")
        if uid not in names:
            try:
                info = client.users_info(user=uid)["user"]
                names[uid] = info.get("real_name") or info.get("name") or uid
            except Exception:
                names[uid] = uid
        return names[uid]

    out = []
    for m in reversed(raw):  # API returns newest first
        if m.get("subtype") in {"channel_join", "channel_leave"} or not m.get("text"):
            continue
        real = datetime.fromtimestamp(float(m["ts"]), tz=timezone.utc)
        text, ts = m["text"], real.isoformat()
        # Seeded messages carry their story date as a "[YYYY-MM-DD] " prefix.
        tag = re.match(r"\[(\d{4}-\d{2}-\d{2})\] ", text)
        if tag:
            text = text[tag.end():]
            ts = f"{tag.group(1)}T{real.strftime('%H:%M:%S')}+00:00"
        out.append({"user": who(m), "text": text, "ts": ts})
    out.sort(key=lambda x: x["ts"])  # stable: same-day messages keep posting order
    return out[:limit]


EXTRACT_PROMPT = """You maintain the memory of a bootcamp content-development copilot.
Read ONE Slack message and return items worth remembering as a JSON array.

Item types:
- {{"kind":"deadline","topic":str,"due_date":"YYYY-MM-DD","owner":str|null,"summary":str}}
  A notebook/module with a due date, or a CHANGED due date for an existing topic.
- {{"kind":"status","topic":str,"status":"done"|"cancelled","summary":str}}
  A topic finished (reviewed and marked done) or dropped. A draft that still needs
  fixes is NOT done.
- {{"kind":"owner","topic":str,"owner":str}}  Someone is assigned a topic.
- {{"kind":"decision","topic":str,"summary":str}}  A rule or choice (dataset, scope, process).
- {{"kind":"feedback","topic":str,"summary":str}}  Reviewer feedback on a specific topic.

Rules:
- Resolve dates like "Oct 19" to ISO using the message date's year ({year}).
- Reuse an existing topic name when the message is about the same thing:
  {topics}
- Use topic "general" for decisions that apply to everything.
- Chit-chat, questions, and acknowledgements with no new fact -> [].
- A message from a content dev confirming an existing deadline adds nothing new -> [].
- Keep summaries under 25 words. Plain ASCII, no dashes except hyphens.

Message date: {ts}
Author: {user}
Message: {text}

Return ONLY the JSON array."""


def _parse_json(raw: str) -> list[dict] | None:
    """Parse the model's JSON array. Returns None when the output is unusable
    (empty, truncated, no array), so callers can tell that apart from a real []."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = text[:-3]
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return [d for d in data if isinstance(d, dict)]


def extract_items(message: dict, known_topics: list[str], model: str = NANO) -> list[dict] | None:
    """Returns None when the model output was unusable (message stays unprocessed)."""
    prompt = EXTRACT_PROMPT.format(
        year=message["ts"][:4],
        topics=", ".join(known_topics) if known_topics else "(none yet)",
        ts=message["ts"],
        user=message["user"],
        text=message["text"],
    )
    # Generous budget: Nemotron may reason before answering, and a message with
    # several deadlines needs a long array. A small cap truncates silently.
    for attempt in (1, 2):
        raw = chat(prompt, model=model, temperature=0.0, max_tokens=4096)
        items = _parse_json(raw)
        if items is not None:
            return items
        print(f"    WARNING: unusable model output (attempt {attempt}): {raw[:120]!r}")
    return None


def apply_items(items: list[dict], message: dict, db_path: str | None = None) -> int:
    """Write extracted items into memory. Returns how many were applied."""
    n = 0
    for it in items:
        kind = it.get("kind")
        topic = it.get("topic") or "general"
        try:
            if kind == "deadline" and it.get("due_date"):
                memory.add_item(
                    "deadline", topic, it.get("summary", ""), message["ts"],
                    owner=it.get("owner"), due_date=it["due_date"],
                    source_user=message["user"], db_path=db_path,
                )
            elif kind == "status" and it.get("status") in {"done", "cancelled"}:
                if memory.set_status(topic, it["status"], db_path) == 0:
                    continue
            elif kind == "owner" and it.get("owner"):
                memory.set_owner(topic, it["owner"], db_path)
            elif kind in {"decision", "feedback"}:
                memory.add_item(
                    kind, topic, it.get("summary", ""), message["ts"],
                    source_user=message["user"], db_path=db_path,
                )
            else:
                continue
            n += 1
        except ValueError:
            continue  # bad date from the model: skip rather than corrupt memory
    return n


def ingest(messages: list[dict], model: str = NANO, db_path: str | None = None,
           verbose: bool = True) -> int:
    """Run extraction over messages in time order and update memory."""
    total = skipped = 0
    for i, msg in enumerate(sorted(messages, key=lambda m: m["ts"]), 1):
        key = memory.msg_key(msg)
        if memory.is_ingested(key, db_path):
            skipped += 1
            continue
        topics = sorted({d["topic"] for s in ("active", "done") for d in
                         memory.list_deadlines(s, db_path)})
        items = extract_items(msg, topics, model=model)
        if items is None:
            continue  # retried on the next run
        applied = apply_items(items, msg, db_path)
        total += applied
        memory.mark_ingested(key, msg["ts"], db_path)
        if verbose:
            print(f"  [{i}] {msg['user'].split(' (')[0]}: {applied} item(s)")
            for it in items:
                print(f"       {it.get('kind')}: {it.get('topic')} {it.get('due_date') or it.get('status') or ''}")
    if verbose:
        print(f"  {skipped} message(s) already ingested, skipped")
    return total
