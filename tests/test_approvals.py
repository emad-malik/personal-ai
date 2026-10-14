"""Offline tests for the approval gate: no Slack, no LLM."""

from __future__ import annotations

import pytest

from copilot import approval_bot, approvals


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr("copilot.memory.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("SLACK_ALLOWED_USERS", "UME")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "CHOME")


class FakeClient:
    def __init__(self, fail_post=False):
        self.posts, self.updates, self.fail_post = [], [], fail_post

    def conversations_open(self, users):
        return {"channel": {"id": "DDM"}}

    def chat_postMessage(self, channel, text, blocks=None):
        if channel != "DDM" and self.fail_post:
            raise RuntimeError("channel_not_found")
        self.posts.append((channel, text))
        return {"ts": "111.1"}

    def chat_update(self, channel, ts, text, blocks):
        self.updates.append((channel, ts, blocks))


def channel_posts(c):
    return [p for p in c.posts if p[0] == "CHOME"]


def test_drafting_never_posts_to_channel():
    c = FakeClient()
    did = approvals.create_draft("Status: all good")
    approval_bot.notify(did, client=c)
    assert channel_posts(c) == []                      # only the DM went out
    assert c.posts[0][0] == "DDM"
    assert approvals.get(did)["status"] == "pending"


def test_dm_has_three_buttons_while_pending():
    did = approvals.create_draft("x")
    blocks = approval_bot.build_blocks(approvals.get(did))
    ids = [e["action_id"] for b in blocks if b["type"] == "actions" for e in b["elements"]]
    assert ids == ["approve_draft", "edit_draft", "discard_draft"]


def test_approve_posts_once_even_on_double_click():
    c = FakeClient()
    did = approvals.create_draft("Hello team")
    approval_bot.notify(did, client=c)
    assert approval_bot.on_approve(c, did, "UME") == "posted"
    assert approval_bot.on_approve(c, did, "UME") == "already_handled"
    assert channel_posts(c) == [("CHOME", "Hello team")]
    assert approvals.get(did)["status"] == "posted"


def test_stranger_cannot_approve():
    c = FakeClient()
    did = approvals.create_draft("secret")
    assert approval_bot.on_approve(c, did, "UEVIL") == "not_allowed"
    assert channel_posts(c) == [] and approvals.get(did)["status"] == "pending"
    assert any(r["action"] == "approve_denied" for r in approvals.audit_log())


def test_discard_blocks_later_approve():
    c = FakeClient()
    did = approvals.create_draft("nope")
    assert approval_bot.on_discard(c, did, "UME") == "discarded"
    assert approval_bot.on_approve(c, did, "UME") == "already_handled"
    assert channel_posts(c) == []


def test_edit_then_approve_posts_edited_text():
    c = FakeClient()
    did = approvals.create_draft("old text")
    approval_bot.notify(did, client=c)
    assert approval_bot.on_edit_submit(c, did, "UME", "new text") == "edited"
    approval_bot.on_approve(c, did, "UME")
    assert channel_posts(c) == [("CHOME", "new text")]


def test_cannot_edit_after_decision():
    c = FakeClient()
    did = approvals.create_draft("a")
    approval_bot.on_discard(c, did, "UME")
    assert approval_bot.on_edit_submit(c, did, "UME", "b") == "not_editable"


def test_failed_post_is_recorded_not_lost():
    c = FakeClient(fail_post=True)
    did = approvals.create_draft("a")
    approval_bot.notify(did, client=c)
    assert approval_bot.on_approve(c, did, "UME") == "failed"
    d = approvals.get(did)
    assert d["status"] == "failed" and "channel_not_found" in d["error"]


def test_audit_trail_covers_the_whole_flow():
    c = FakeClient()
    did = approvals.create_draft("a")
    approval_bot.notify(did, client=c)
    approval_bot.on_approve(c, did, "UME")
    actions = [r["action"] for r in reversed(approvals.audit_log())]
    assert actions == ["draft_created", "approval_requested", "draft_approved",
                       "posted_to_channel"]


def test_empty_draft_rejected():
    with pytest.raises(ValueError):
        approvals.create_draft("   ")


def test_status_update_text(tmp_path):
    from datetime import date
    from copilot import memory, planner
    db = str(tmp_path / "s.db")
    memory.add_item("deadline", "KNN", "d", "2026-10-03T09:00", owner="Lena",
                    due_date="2026-10-28", db_path=db)
    memory.add_item("deadline", "Cleaning", "d", "2026-10-01T09:00", owner="Lena",
                    due_date="2026-10-21", db_path=db)
    memory.set_status("Cleaning", "done", db)
    t = planner.status_update(date(2026, 10, 16), db)
    assert "Done: Cleaning" in t and "KNN, due 2026-10-28, Lena" in t


def test_draft_post_cli_default_sends_no_dm(monkeypatch):
    import argparse
    from copilot import cli

    monkeypatch.setattr(approval_bot, "notify",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no DM expected")))
    cli.cmd_draft_post(argparse.Namespace(text="hi", channel="home", buttons=False))
    assert approvals.list_by_status("pending")[0]["body"] == "hi"


def test_approve_cli_posts_after_decision(monkeypatch, capsys):
    import argparse
    from copilot import cli

    c = FakeClient()
    monkeypatch.setattr(cli, "_slack_client", lambda: c)
    did = approvals.create_draft("ship it")
    cli.cmd_approve(argparse.Namespace(id=did))
    cli.cmd_approve(argparse.Namespace(id=did))          # second call must not repost
    assert channel_posts(c) == [("CHOME", "ship it")]
    assert "already handled" in capsys.readouterr().out
