"""Pure logic for the content-copilot Hermes plugin (no Hermes imports, so it is testable).

Three jobs:
1. Tool handlers that run our own code (status text comes from memory, not the model).
2. An approval gate: copilot_approve only works after the person answered the
   clarify question for that exact draft with "Approve". The model cannot forge that
   answer because the hook reads it from the clarify tool result.
3. Rules that block other ways of posting to Slack, and an audit trail of tool calls.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
AUDIT_FILE = REPO / "outputs" / "tool_audit.jsonl"
GRANT_TTL = 900  # seconds an Approve answer stays valid

FORBIDDEN = [
    (r"copilot\.cli\s+(approve|discard|edit)\b",
     "Use the copilot_approve / copilot_discard / copilot_edit tools, not the shell."),
    (r"hermes\s+send\b", "Sending to Slack from the shell is not allowed. Use the draft tools."),
    (r"chat[._]post(message|ephemeral)", "Posting to Slack directly is not allowed. Use the draft tools."),
    (r"files[._]upload", "Uploading to Slack directly is not allowed. Use the copilot.cli send-file command."),
    (r"slack\.com/api", "Calling the Slack API directly is not allowed."),
]


# ---------------------------------------------------------------- helpers
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for v in obj.values() for t in _strings(v)]
    if isinstance(obj, (list, tuple)):
        return [t for v in obj for t in _strings(v)]
    return []


def redact(text: str) -> str:
    text = re.sub(r"xox[a-z]-[\w-]+", "[slack-token]", text)
    text = re.sub(r"xapp-[\w-]+", "[slack-app-token]", text)
    return re.sub(r"v1\.[A-Za-z0-9_\-.]{40,}", "[api-key]", text)


def audit_write(event: dict, path: Path | None = None) -> None:
    """Append one line to the tool audit file. Never raises: hooks must not break the agent."""
    try:
        path = path or AUDIT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **event}
        with open(path, "a", encoding="utf-8") as f:
            f.write(redact(json.dumps(event, ensure_ascii=False)) + "\n")
    except Exception:  # noqa: BLE001
        pass


def check_forbidden(tool_name: str, args) -> str | None:
    """Return a block message if this tool call tries to post to Slack some other way."""
    if (tool_name or "").startswith("copilot_"):
        return None
    blob = " ".join(_strings(args)).lower()
    for pattern, message in FORBIDDEN:
        if re.search(pattern, blob):
            return message
    return None


def _parse_result(result):
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            data = json.loads(result)
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}
    return {}


# ---------------------------------------------------------------- gate
class Gate:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.bodies: dict[int, str] = {}
        self.answers: dict[int, tuple[str, float]] = {}
        self.lock = threading.Lock()

    def note_draft(self, draft_id: int, body: str) -> None:
        with self.lock:
            self.bodies[draft_id] = body
            self.answers.pop(draft_id, None)  # any earlier answer belonged to older text

    def on_clarify(self, params, result) -> list[tuple[int, str]]:
        """Record decisions from a finished clarify call. Returns [(draft_id, answer)]."""
        data = _parse_result(result)
        questions = (params or {}).get("questions") or []
        recorded = []
        for i, resp in enumerate(data.get("responses") or []):
            if not isinstance(resp, dict) or resp.get("status") != "answered":
                continue
            answer = _norm(str(resp.get("user_response", "")))
            if answer not in {"approve", "edit", "discard"}:
                continue
            asked = " ".join(_strings(questions[i])) if i < len(questions) else ""
            shown = " ".join([asked] + [t for k, t in resp.items()
                                        if k not in {"user_response", "status"}
                                        for t in _strings(t)])
            ids = set(re.findall(r"#(\d+)", asked))
            if len(ids) != 1:
                continue
            draft_id = int(ids.pop())
            body = self.bodies.get(draft_id)
            if body is None or _norm(body) not in _norm(shown):
                continue  # the person was not shown the exact draft text
            with self.lock:
                self.answers[draft_id] = (answer, self.clock())
            recorded.append((draft_id, answer))
        return recorded

    def consume(self, draft_id: int, decision: str) -> bool:
        with self.lock:
            got = self.answers.get(draft_id)
            if not got or got[0] != decision or self.clock() - got[1] > GRANT_TTL:
                return False
            del self.answers[draft_id]
            return True


GATE = Gate()


# ---------------------------------------------------------------- CLI bridge
def run_cli(*args: str, timeout: int = 120) -> dict:
    venv_python = REPO / ".venv" / "bin" / "python"
    if venv_python.exists():
        cmd = [str(venv_python), "-m", "copilot.cli", *args]
    else:
        cmd = [shutil.which("uv") or "uv", "run", "python", "-m", "copilot.cli", *args]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    pylibs = os.getenv("COPILOT_PYLIBS") or ("/sandbox/pylibs" if Path("/sandbox/pylibs").is_dir() else "")
    if pylibs and not venv_python.exists():
        cmd = [sys.executable, "-m", "copilot.cli", *args]
        env["PYTHONPATH"] = f"{pylibs}:{REPO}"
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout,
                           env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "", "error": f"timed out after {timeout}s"}
    return {"ok": p.returncode == 0, "output": p.stdout[-6000:], "error": p.stderr[-800:]}


def _draft_from(out: dict) -> dict | None:
    for line in reversed(out["output"].splitlines()):
        if line.startswith("DRAFT_JSON "):
            return json.loads(line[len("DRAFT_JSON "):])
    return None


ASK_NEXT = ("Now call the clarify tool with ONE question that contains the line "
            "'Draft #{id}' and the full draft text copied exactly, with choices exactly "
            "['Approve', 'Edit', 'Discard']. Do not ask anything else first.")


def _drafted(out: dict, gate: Gate) -> str:
    draft = _draft_from(out) if out["ok"] else None
    if not draft:
        return json.dumps({"success": False, "error": out["error"] or out["output"]})
    gate.note_draft(draft["id"], draft["text"])
    return json.dumps({"success": True, "draft_id": draft["id"], "draft_text": draft["text"],
                       "posted": False, "next_step": ASK_NEXT.format(id=draft["id"])})


# ---------------------------------------------------------------- tool handlers
def make_handlers(gate: Gate = GATE, runner=run_cli) -> dict:
    def refresh(params, **kw):
        out = runner("ingest", "--slack", timeout=420)
        return json.dumps({"success": out["ok"], "detail": out["output"][-400:] or out["error"]})

    def plan(params, **kw):
        extra = ["--today", params["today"]] if params.get("today") else []
        out = runner("plan", *extra)
        return json.dumps({"success": out["ok"], "plan": out["output"] or out["error"]})

    def draft_status(params, **kw):
        extra = ["--note", params["note"]] if params.get("note") else []
        return _drafted(runner("draft-status", *extra), gate)

    def draft_post(params, **kw):
        return _drafted(runner("draft-post", params.get("text", "")), gate)

    def approve(params, **kw):
        did = int(params["draft_id"])
        if not gate.consume(did, "approve"):
            return json.dumps({"success": False, "posted": False, "error": (
                f"Draft #{did} has no fresh Approve answer from the person. Ask with the "
                "clarify tool (draft text included, choices Approve/Edit/Discard) and call "
                "this again only if they pick Approve.")})
        out = runner("approve", str(did))
        return json.dumps({"success": out["ok"], "result": out["output"].strip() or out["error"]})

    def discard(params, **kw):
        out = runner("discard", str(int(params["draft_id"])))
        return json.dumps({"success": out["ok"], "result": out["output"].strip() or out["error"]})

    def edit(params, **kw):
        did = int(params["draft_id"])
        out = runner("edit", str(did), params["new_text"])
        if out["ok"]:
            gate.note_draft(did, params["new_text"].strip())
        return json.dumps({"success": out["ok"], "posted": False,
                           "result": out["output"].strip() or out["error"],
                           "next_step": ASK_NEXT.format(id=did) if out["ok"] else ""})

    return {"copilot_refresh_memory": refresh, "copilot_plan": plan,
            "copilot_draft_status": draft_status, "copilot_draft_post": draft_post,
            "copilot_approve": approve, "copilot_discard": discard, "copilot_edit": edit}


def _schema(name: str, description: str, props: dict | None = None, required=()) -> dict:
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": props or {},
                           "required": list(required)}}


SCHEMAS = {
    "copilot_refresh_memory": _schema(
        "copilot_refresh_memory",
        "Re-read the team Slack channel and rebuild the deadline/decision memory. Takes about a "
        "minute. Call before copilot_plan or drafting a status update if memory may be stale."),
    "copilot_plan": _schema(
        "copilot_plan",
        "Return the exact plan from memory: due list, what changed, what to build next. Do not "
        "recompute dates yourself.", {"today": {"type": "string", "description": "YYYY-MM-DD, optional"}}),
    "copilot_draft_status": _schema(
        "copilot_draft_status",
        "Draft the weekly channel status update from memory and put it in the approval queue. "
        "Posts NOTHING. Do not ask the person questions first: the text is built from memory. "
        "'note' is appended word for word. Never invent content.",
        {"note": {"type": "string", "description": "Optional extra line the person dictated"}}),
    "copilot_draft_post": _schema(
        "copilot_draft_post",
        "Put a message the person dictated into the approval queue. Posts NOTHING. Keep their words.",
        {"text": {"type": "string"}}, ["text"]),
    "copilot_approve": _schema(
        "copilot_approve",
        "Post a queued draft to the team channel. Works ONLY after the person answered Approve to "
        "a clarify question showing that draft. Otherwise it refuses.",
        {"draft_id": {"type": "integer"}}, ["draft_id"]),
    "copilot_discard": _schema(
        "copilot_discard", "Discard a queued draft. Posts nothing.",
        {"draft_id": {"type": "integer"}}, ["draft_id"]),
    "copilot_edit": _schema(
        "copilot_edit",
        "Replace the text of a queued draft with the person's new wording. Posts nothing and "
        "requires a new Approve afterwards.",
        {"draft_id": {"type": "integer"}, "new_text": {"type": "string"}},
        ["draft_id", "new_text"]),
}


# ---------------------------------------------------------------- hooks
def pre_tool_call(tool_name, args, task_id=None, gate: Gate = GATE, **kwargs):
    message = check_forbidden(tool_name, args)
    if message:
        audit_write({"tool": tool_name, "outcome": "blocked", "reason": message,
                     "args": json.dumps(args, default=str)[:300]})
        return {"action": "block", "message": message}
    return None


def post_tool_call(tool_name, params=None, result=None, gate: Gate = GATE, **kwargs):
    params = params if params is not None else kwargs.get("args")
    event = {"tool": tool_name, "outcome": "ok", "args": json.dumps(params, default=str)[:300]}
    if tool_name == "clarify":
        recorded = gate.on_clarify(params if isinstance(params, dict) else {}, result)
        event["gate"] = recorded
        event["result_preview"] = str(result)[:400]  # to confirm the real result shape
    audit_write(event)
