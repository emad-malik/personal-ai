"""Approval queue for outbound channel posts.

Stage 4: the agent can only DRAFT a post. A draft stays 'pending' until the human
presses Approve in Slack. State machine (each step is a single guarded UPDATE, so a
double click cannot post twice):

    pending -> approved -> posted | failed
    pending -> discarded
"""

from __future__ import annotations

from datetime import datetime, timezone

from copilot.memory import connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def audit(actor: str, action: str, detail: str = "", db_path: str | None = None) -> None:
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO audit_log(ts, actor, action, detail) VALUES (?,?,?,?)",
            (_now(), actor, action, detail),
        )


def audit_log(limit: int = 50, db_path: str | None = None) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def create_draft(body: str, channel: str = "home", db_path: str | None = None) -> int:
    if not body.strip():
        raise ValueError("Draft body is empty")
    with connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO approvals(body, channel, created_ts) VALUES (?,?,?)",
            (body.strip(), channel, _now()),
        )
        draft_id = cur.lastrowid
    audit("agent", "draft_created", f"#{draft_id} -> {channel}", db_path)
    return draft_id


def get(draft_id: int, db_path: str | None = None) -> dict | None:
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM approvals WHERE id=?", (draft_id,)).fetchone()
    return dict(row) if row else None


def list_by_status(status: str | None = "pending", db_path: str | None = None) -> list[dict]:
    with connect(db_path) as con:
        if status:
            rows = con.execute(
                "SELECT * FROM approvals WHERE status=? ORDER BY id", (status,)
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM approvals ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def set_dm_ref(draft_id: int, dm_channel: str, dm_ts: str, db_path: str | None = None) -> None:
    with connect(db_path) as con:
        con.execute("UPDATE approvals SET dm_channel=?, dm_ts=? WHERE id=?",
                    (dm_channel, dm_ts, draft_id))


def edit(draft_id: int, body: str, actor: str, db_path: str | None = None) -> bool:
    """Replace the text of a pending draft. Returns False if it is no longer pending."""
    if not body.strip():
        return False
    with connect(db_path) as con:
        cur = con.execute(
            "UPDATE approvals SET body=? WHERE id=? AND status='pending'",
            (body.strip(), draft_id),
        )
        changed = cur.rowcount == 1
    if changed:
        audit(actor, "draft_edited", f"#{draft_id}", db_path)
    return changed


def decide(draft_id: int, status: str, actor: str, db_path: str | None = None) -> bool:
    """Move pending -> approved|discarded. True only for the first caller."""
    if status not in {"approved", "discarded"}:
        raise ValueError(status)
    with connect(db_path) as con:
        cur = con.execute(
            "UPDATE approvals SET status=?, decided_ts=?, decided_by=? "
            "WHERE id=? AND status='pending'",
            (status, _now(), actor, draft_id),
        )
        won = cur.rowcount == 1
    audit(actor, f"draft_{status}" if won else f"draft_{status}_ignored",
          f"#{draft_id}", db_path)
    return won


def mark_posted(draft_id: int, db_path: str | None = None) -> None:
    with connect(db_path) as con:
        con.execute("UPDATE approvals SET status='posted', posted_ts=? WHERE id=?",
                    (_now(), draft_id))
    audit("copilot", "posted_to_channel", f"#{draft_id}", db_path)


def mark_failed(draft_id: int, error: str, db_path: str | None = None) -> None:
    with connect(db_path) as con:
        con.execute("UPDATE approvals SET status='failed', error=? WHERE id=?",
                    (error[:300], draft_id))
    audit("copilot", "post_failed", f"#{draft_id}: {error[:120]}", db_path)
