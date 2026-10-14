"""Daily plan generator.

Stage 2: deterministic plan from memory. No LLM call, so the due list is exact.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

from copilot import memory


def _slug(topic: str) -> str:
    return topic.lower().replace(" ", "_").replace("/", "_")[:60]


def notebook_exists(topic: str, output_dir: str = "outputs") -> bool:
    return os.path.exists(os.path.join(output_dir, f"{_slug(topic)}.ipynb"))


def due_list(today: date, db_path: str | None = None) -> list[dict]:
    """Active deadlines sorted by date, each with days_left and previous date if changed."""
    out = []
    for d in memory.list_deadlines("active", db_path):
        due = date.fromisoformat(d["due_date"])
        out.append({
            **d,
            "days_left": (due - today).days,
            "was": memory.previous_due(d["topic"], db_path),
        })
    return out


def next_to_build(today: date, db_path: str | None = None, output_dir: str = "outputs"):
    for d in due_list(today, db_path):
        if not notebook_exists(d["topic"], output_dir):
            return d
    return None


def generate_plan(today: date | None = None, db_path: str | None = None,
                  output_dir: str = "outputs") -> str:
    today = today or date.today()
    items = due_list(today, db_path)
    lines = [f"Plan for {today.strftime('%a %b %d, %Y')}", ""]

    lines.append("Due (soonest first):")
    if not items:
        lines.append("  nothing scheduled")
    for d in items:
        when = ("OVERDUE" if d["days_left"] < 0
                else "today" if d["days_left"] == 0
                else f"in {d['days_left']}d")
        note = f" (moved from {d['was']})" if d["was"] and d["was"] != d["due_date"] else ""
        lines.append(f"  {d['due_date']}  {d['topic']}  [{d['owner'] or 'unassigned'}]  {when}{note}")

    since = (datetime.combine(today, datetime.min.time()) - timedelta(days=1)).isoformat()
    recent = [i for i in memory.changed_since(since, db_path)]
    lines += ["", "Changed since yesterday:"]
    lines += [f"  {i['kind']}: {i['topic']}: {i['summary']}" for i in recent] or ["  nothing new"]

    done = memory.list_deadlines("done", db_path)
    cancelled = memory.list_deadlines("cancelled", db_path)
    if done:
        lines += ["", "Done: " + ", ".join(d["topic"] for d in done)]
    if cancelled:
        lines += ["Cancelled: " + ", ".join(d["topic"] for d in cancelled)]

    nxt = next_to_build(today, db_path, output_dir)
    lines += ["", "Proposed build today:"]
    if nxt:
        ctx = memory.query_context(nxt["topic"], db_path)
        lines.append(f"  {nxt['topic']} (due {nxt['due_date']})")
        for c in ctx:
            lines.append(f"    - {c['kind']}: {c['summary']}")
    else:
        lines.append("  nothing to build")
    return "\n".join(lines)


def build_constraints(topic: str, db_path: str | None = None) -> str:
    """Turn remembered decisions and feedback into a constraints string for the generator."""
    ctx = memory.query_context(topic, db_path)
    return "; ".join(re.sub(r"\s+", " ", c["summary"]) for c in ctx)


def status_update(today: date | None = None, db_path: str | None = None) -> str:
    """Plain-text weekly status for the channel, built from memory (no LLM)."""
    today = today or date.today()
    items = due_list(today, db_path)
    done = memory.list_deadlines("done", db_path)
    cancelled = memory.list_deadlines("cancelled", db_path)
    lines = [f"Content status for the week of {today.strftime('%b %d, %Y')}", ""]
    lines.append("Done: " + (", ".join(d["topic"] for d in done) or "nothing yet"))
    lines.append("Coming up:")
    for d in items:
        moved = f", moved from {d['was']}" if d["was"] and d["was"] != d["due_date"] else ""
        lines.append(f"- {d['topic']}, due {d['due_date']}, {d['owner'] or 'unassigned'}{moved}")
    if cancelled:
        lines.append("Dropped: " + ", ".join(d["topic"] for d in cancelled))
    return "\n".join(lines)
