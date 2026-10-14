"""Offline tests: memory + planner, no LLM or Slack needed."""

from __future__ import annotations

import json
from datetime import date

from copilot import memory, planner, slack_reader

DB_KW = {}


def _replay(db):
    """Apply the known-correct extraction for the seed story, without an LLM."""
    A = lambda *a, **k: memory.add_item(*a, db_path=db, **k)  # noqa: E731
    A("deadline", "Pandas Basics", "due", "2026-10-01T09:00", owner="Omar", due_date="2026-10-19")
    A("deadline", "Data Cleaning and EDA", "due", "2026-10-01T09:00", owner="Lena", due_date="2026-10-21")
    A("deadline", "Linear Regression", "due", "2026-10-03T09:10", owner="Omar", due_date="2026-10-23")
    A("deadline", "KNN Classification", "due", "2026-10-03T09:10", owner="Lena", due_date="2026-10-28")
    A("deadline", "K-Means Clustering", "due", "2026-10-03T09:10", owner="Omar", due_date="2026-10-30")
    A("deadline", "Feature Scaling", "due", "2026-10-03T09:10", due_date="2026-10-27")
    A("decision", "general", "Use Titanic throughout week 3, no deep learning", "2026-10-06T11:00")
    A("deadline", "Linear Regression", "moved", "2026-10-09T10:00", due_date="2026-10-26")
    memory.set_status("Feature Scaling", "cancelled", db)
    A("deadline", "Model Evaluation", "new", "2026-10-13T09:00", owner="Lena", due_date="2026-11-04")
    A("feedback", "Pandas Basics", "Conclusion must compare pandas, Polars, SQL", "2026-10-15T10:00")
    memory.set_status("Data Cleaning and EDA", "done", db)


def test_plan_matches_expected(tmp_path):
    db = str(tmp_path / "m.db")
    _replay(db)
    exp = json.load(open("demo/expected_plan.json", encoding="utf-8"))
    today = date.fromisoformat(exp["as_of"])
    got = [(d["topic"], d["due_date"], d["owner"]) for d in planner.due_list(today, db)]
    want = [(d["topic"], d["due"], d["owner"]) for d in exp["active_deadlines"]]
    assert got == want


def test_changed_deadline_keeps_history(tmp_path):
    db = str(tmp_path / "m.db")
    _replay(db)
    assert memory.previous_due("Linear Regression", db) == "2026-10-23"
    text = planner.generate_plan(date(2026, 10, 17), db, output_dir=str(tmp_path))
    assert "moved from 2026-10-23" in text
    assert "Cancelled: Feature Scaling" in text


def test_context_includes_general_and_topic(tmp_path):
    db = str(tmp_path / "m.db")
    _replay(db)
    c = planner.build_constraints("Pandas Basics", db)
    assert "Titanic" in c and "Polars" in c


def test_bad_date_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        memory.add_item("deadline", "X", "s", "2026-10-01", due_date="Oct 19",
                        db_path=str(tmp_path / "m.db"))


def test_apply_items_skips_bad_model_output(tmp_path):
    db = str(tmp_path / "m.db")
    msg = {"user": "Maya", "text": "x", "ts": "2026-10-01T09:00:00Z"}
    n = slack_reader.apply_items(
        [{"kind": "deadline", "topic": "A", "due_date": "soon"},
         {"kind": "deadline", "topic": "B", "due_date": "2026-10-19", "summary": "ok"}],
        msg, db)
    assert n == 1


def test_seed_file_loads():
    msgs = slack_reader.load_seed()
    assert len(msgs) == 28 and {"user", "text", "ts"} <= set(msgs[0])


def test_parse_json_handles_think_fences_and_truncation():
    assert slack_reader._parse_json("<think>hmm [x]</think>```json\n[]\n```") == []
    assert slack_reader._parse_json('[{"kind":"decision","topic":"general"}]')[0]["kind"] == "decision"
    assert slack_reader._parse_json('[{"kind":"deadline","topic":"A"') is None  # truncated
    assert slack_reader._parse_json("") is None


def test_send_file_uses_dm_and_uploads(tmp_path, monkeypatch):
    from copilot import slack_send

    f = tmp_path / "a.ipynb"
    f.write_text("{}")
    monkeypatch.setenv("SLACK_ALLOWED_USERS", "U123,U456")

    class FakeClient:
        def conversations_open(self, users):
            assert users == "U123"
            return {"channel": {"id": "D1"}}

        def files_upload_v2(self, **kw):
            assert kw["channel"] == "D1" and kw["title"] == "a.ipynb"
            return {"file": {"permalink": "https://x/y"}}

    assert slack_send.upload_file(str(f), client=FakeClient()) == "https://x/y"


def test_send_file_missing(tmp_path):
    import pytest
    from copilot import slack_send
    with pytest.raises(FileNotFoundError):
        slack_send.upload_file(str(tmp_path / "nope.ipynb"), client=object())


def test_send_file_to_channel_thread_and_home(tmp_path, monkeypatch):
    from copilot import slack_send

    f = tmp_path / "a.ipynb"
    f.write_text("{}")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C99")
    seen = {}

    class FakeClient:
        def conversations_open(self, users):
            raise AssertionError("must not open a DM for a channel upload")

        def files_upload_v2(self, **kw):
            seen.update(kw)
            return {"file": {"permalink": "p"}}

    slack_send.upload_file(str(f), channel="home", thread_ts="1.2", client=FakeClient())
    assert seen["channel"] == "C99" and seen["thread_ts"] == "1.2"
    slack_send.upload_file(str(f), channel="C5", client=FakeClient())
    assert seen["channel"] == "C5" and seen["thread_ts"] is None


def test_ingest_skips_already_processed(tmp_path, monkeypatch):
    from copilot import slack_reader
    db = str(tmp_path / "m.db")
    calls = []
    monkeypatch.setattr(slack_reader, "extract_items",
                        lambda msg, topics, model=None: calls.append(msg["text"]) or [])
    msgs = [{"user": "A", "text": "hi", "ts": "2026-10-01T00:00:00+00:00"}]
    slack_reader.ingest(msgs, db_path=db, verbose=False)
    slack_reader.ingest(msgs + [{"user": "A", "text": "new", "ts": "2026-10-02T00:00:00+00:00"}],
                        db_path=db, verbose=False)
    assert calls == ["hi", "new"]


def test_failed_extraction_is_retried(tmp_path, monkeypatch):
    from copilot import slack_reader
    db = str(tmp_path / "m.db")
    results = iter([None, []])
    monkeypatch.setattr(slack_reader, "extract_items", lambda *a, **k: next(results))
    msgs = [{"user": "A", "text": "hi", "ts": "2026-10-01T00:00:00+00:00"}]
    slack_reader.ingest(msgs, db_path=db, verbose=False)
    slack_reader.ingest(msgs, db_path=db, verbose=False)
    assert next(results, "exhausted") == "exhausted"
