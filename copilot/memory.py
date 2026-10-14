"""Persistent memory in SQLite.

Stage 2: exact-date deadlines plus free-text decisions and feedback.
One table, append-only history. Deadlines are keyed by topic; a newer
message for the same topic supersedes the older one.
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date

DB_PATH = os.getenv("COPILOT_DB", os.path.join("outputs", "memory.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,            -- deadline | decision | feedback
    topic TEXT NOT NULL,
    owner TEXT,
    due_date TEXT,                 -- ISO date, deadlines only
    status TEXT NOT NULL DEFAULT 'active',  -- active | done | cancelled | superseded
    summary TEXT NOT NULL,
    source_user TEXT,
    source_ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_kind_status ON items(kind, status);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    body TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'home',
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | posted | failed | discarded
    created_ts TEXT NOT NULL,
    decided_ts TEXT,
    decided_by TEXT,
    posted_ts TEXT,
    error TEXT,
    dm_channel TEXT,
    dm_ts TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT
);
"""


def norm(topic: str) -> str:
    """Normalise a topic so 'KNN classification' and 'knn  Classification' match."""
    return re.sub(r"\s+", " ", topic.strip().lower())


@contextmanager
def connect(db_path: str | None = None):
    path = db_path or DB_PATH
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def reset(db_path: str | None = None) -> None:
    with connect(db_path) as con:
        con.execute("DELETE FROM items")


def add_item(
    kind: str,
    topic: str,
    summary: str,
    source_ts: str,
    *,
    owner: str | None = None,
    due_date: str | None = None,
    source_user: str | None = None,
    db_path: str | None = None,
) -> int:
    """Insert an item. A new deadline supersedes the active one for that topic."""
    if due_date:
        date.fromisoformat(due_date)  # raises on a malformed date
    with connect(db_path) as con:
        if kind == "deadline":
            con.execute(
                "UPDATE items SET status='superseded' "
                "WHERE kind='deadline' AND status='active' AND lower(topic)=?",
                (norm(topic),),
            )
            if owner is None:
                row = con.execute(
                    "SELECT owner FROM items WHERE kind='deadline' AND lower(topic)=? "
                    "AND owner IS NOT NULL ORDER BY id DESC LIMIT 1",
                    (norm(topic),),
                ).fetchone()
                owner = row["owner"] if row else None
        cur = con.execute(
            "INSERT INTO items(kind, topic, owner, due_date, summary, source_user, source_ts) "
            "VALUES (?,?,?,?,?,?,?)",
            (kind, topic.strip(), owner, due_date, summary, source_user, source_ts),
        )
        return cur.lastrowid


def set_status(topic: str, status: str, db_path: str | None = None) -> int:
    """Mark the active deadline for a topic done or cancelled. Returns rows changed."""
    with connect(db_path) as con:
        cur = con.execute(
            "UPDATE items SET status=? WHERE kind='deadline' AND status='active' "
            "AND lower(topic)=?",
            (status, norm(topic)),
        )
        return cur.rowcount


def set_owner(topic: str, owner: str, db_path: str | None = None) -> None:
    with connect(db_path) as con:
        con.execute(
            "UPDATE items SET owner=? WHERE kind='deadline' AND status='active' "
            "AND lower(topic)=?",
            (owner, norm(topic)),
        )


def list_deadlines(status: str = "active", db_path: str | None = None) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM items WHERE kind='deadline' AND status=? "
            "ORDER BY due_date, topic",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_items(kind: str, db_path: str | None = None) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM items WHERE kind=? AND status='active' ORDER BY source_ts",
            (kind,),
        ).fetchall()
    return [dict(r) for r in rows]


def previous_due(topic: str, db_path: str | None = None) -> str | None:
    """The due date a topic had before it was last changed, if any."""
    with connect(db_path) as con:
        row = con.execute(
            "SELECT due_date FROM items WHERE kind='deadline' AND status='superseded' "
            "AND lower(topic)=? ORDER BY id DESC LIMIT 1",
            (norm(topic),),
        ).fetchone()
    return row["due_date"] if row else None


def changed_since(since_iso: str, db_path: str | None = None) -> list[dict]:
    """All items from messages at or after since_iso (any status)."""
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM items WHERE source_ts >= ? ORDER BY source_ts", (since_iso,)
        ).fetchall()
    return [dict(r) for r in rows]


def query_context(topic: str, db_path: str | None = None) -> list[dict]:
    """Decisions and feedback relevant to a topic, plus global ones (topic 'general')."""
    key = norm(topic)
    out = []
    for kind in ("decision", "feedback"):
        for it in list_items(kind, db_path):
            t = norm(it["topic"])
            if t == "general" or t in key or key in t:
                out.append(it)
    return out
