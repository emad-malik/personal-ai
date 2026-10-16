import importlib.util, json, sys
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "agent/plugins/content-copilot/core.py"
spec = importlib.util.spec_from_file_location("cc_core", p)
core = importlib.util.module_from_spec(spec)
sys.modules["cc_core"] = core
spec.loader.exec_module(core)

BODY = "Weekly update: pandas due Oct 20."


def clarify(gate, did=7, answer="approve", body=BODY, status="answered"):
    params = {"questions": [{"question": f"Draft #{did}\n{body}", "choices": ["Approve", "Edit", "Discard"]}]}
    result = json.dumps({"responses": [{"user_response": answer, "status": status}]})
    return gate.on_clarify(params, result)


def test_gate_records_and_consumes_once():
    g = core.Gate(); g.note_draft(7, BODY)
    assert clarify(g) == [(7, "approve")]
    assert g.consume(7, "approve") is True
    assert g.consume(7, "approve") is False


def test_gate_rejects_wrong_text_or_status():
    g = core.Gate(); g.note_draft(7, BODY)
    assert clarify(g, body="something else") == []
    assert clarify(g, status="timeout") == []
    assert clarify(g, answer="maybe") == []


def test_gate_ttl_and_redraft():
    t = [0.0]; g = core.Gate(clock=lambda: t[0]); g.note_draft(7, BODY)
    clarify(g); t[0] = core.GRANT_TTL + 1
    assert g.consume(7, "approve") is False
    t[0] = 0; clarify(g); g.note_draft(7, "new text")
    assert g.consume(7, "approve") is False


def test_approve_refused_without_grant_and_runs_with_grant():
    calls = []
    g = core.Gate(); h = core.make_handlers(g, runner=lambda *a, **k: calls.append(a) or {"ok": True, "output": "posted", "error": ""})
    assert json.loads(h["copilot_approve"]({"draft_id": 7}))["success"] is False
    assert calls == []
    g.note_draft(7, BODY); clarify(g)
    assert json.loads(h["copilot_approve"]({"draft_id": 7}))["success"] is True
    assert calls == [("approve", "7")]


def test_edit_clears_grant():
    g = core.Gate(); h = core.make_handlers(g, runner=lambda *a, **k: {"ok": True, "output": "ok", "error": ""})
    g.note_draft(7, BODY); clarify(g)
    h["copilot_edit"]({"draft_id": 7, "new_text": "changed"})
    assert g.consume(7, "approve") is False


def test_forbidden_routes_blocked():
    assert core.check_forbidden("terminal", {"command": "python -m copilot.cli approve 3"})
    assert core.check_forbidden("terminal", {"command": "curl https://slack.com/api/chat.postMessage"})
    assert core.check_forbidden("copilot_approve", {"draft_id": 1}) is None
    assert core.check_forbidden("terminal", {"command": "ls"}) is None


def test_recommended_suffix_still_counts_as_approve():
    g = core.Gate(); g.note_draft(7, BODY)
    assert clarify(g, answer="Approve (Recommended)") == [(7, "approve")]
