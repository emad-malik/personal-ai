"""Slack side of the approval gate: DM with Approve / Edit / Discard buttons.

Nothing reaches the channel unless the human presses Approve. Only Slack member IDs in
SLACK_ALLOWED_USERS may press the buttons.

Tokens: APPROVAL_BOT_TOKEN / APPROVAL_APP_TOKEN if set, else SLACK_BOT_TOKEN /
SLACK_APP_TOKEN. Use a separate Slack app for this listener when Hermes runs on the
main app: Slack splits events between all Socket Mode connections of one app.

Run the listener:  python -m copilot.approval_bot
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from copilot import approvals

load_dotenv()

APPROVE, EDIT, DISCARD = "approve_draft", "edit_draft", "discard_draft"
EDIT_MODAL = "edit_draft_modal"


def _allowed() -> list[str]:
    return [u.strip() for u in os.getenv("SLACK_ALLOWED_USERS", "").split(",") if u.strip()]


def is_allowed(user_id: str) -> bool:
    return user_id in _allowed()


def resolve_channel(draft: dict) -> str:
    if draft["channel"] == "home":
        channel = os.getenv("SLACK_CHANNEL_ID")
        if not channel:
            raise RuntimeError("SLACK_CHANNEL_ID is not set")
        return channel
    return draft["channel"]


def build_blocks(draft: dict) -> list[dict]:
    body = draft["body"][:2800]
    status = draft["status"]
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"*Draft post #{draft['id']} for the channel* ({status})"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": body}},
    ]
    if status == "pending":
        value = str(draft["id"])
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Approve"},
             "style": "primary", "action_id": APPROVE, "value": value},
            {"type": "button", "text": {"type": "plain_text", "text": "Edit"},
             "action_id": EDIT, "value": value},
            {"type": "button", "text": {"type": "plain_text", "text": "Discard"},
             "style": "danger", "action_id": DISCARD, "value": value},
        ]})
        note = "Nothing is posted until you press Approve."
    elif status == "posted":
        note = "Approved and posted to the channel."
    elif status == "discarded":
        note = "Discarded. Nothing was posted."
    elif status == "failed":
        note = f"Approved but the post failed: {draft.get('error')}"
    else:
        note = f"Status: {status}"
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": note}]})
    return blocks


def _refresh(client, draft_id: int) -> None:
    d = approvals.get(draft_id)
    if d and d.get("dm_channel") and d.get("dm_ts"):
        client.chat_update(channel=d["dm_channel"], ts=d["dm_ts"],
                           text=f"Draft post #{d['id']} ({d['status']})",
                           blocks=build_blocks(d))


def notify(draft_id: int, client=None, user_id: str | None = None) -> str:
    """DM the approver the draft with buttons. Returns the DM message timestamp."""
    if client is None:
        from slack_sdk import WebClient

        client = WebClient(token=os.getenv("APPROVAL_BOT_TOKEN") or os.getenv("SLACK_BOT_TOKEN"))
    user_id = user_id or (_allowed() or [None])[0]
    if not user_id:
        raise RuntimeError("Set SLACK_ALLOWED_USERS in .env")
    d = approvals.get(draft_id)
    dm = client.conversations_open(users=user_id)["channel"]["id"]
    resp = client.chat_postMessage(channel=dm, text=f"Draft post #{draft_id} needs your approval",
                                   blocks=build_blocks(d))
    approvals.set_dm_ref(draft_id, dm, resp["ts"])
    approvals.audit("copilot", "approval_requested", f"#{draft_id} sent to DM")
    return resp["ts"]


def on_approve(client, draft_id: int, actor: str) -> str:
    if not is_allowed(actor):
        approvals.audit(actor, "approve_denied", f"#{draft_id}: user not allowed")
        return "not_allowed"
    if not approvals.decide(draft_id, "approved", actor):
        return "already_handled"
    d = approvals.get(draft_id)
    try:
        client.chat_postMessage(channel=resolve_channel(d), text=d["body"])
        approvals.mark_posted(draft_id)
        result = "posted"
    except Exception as e:  # noqa: BLE001 - surface any Slack/network error to the human
        approvals.mark_failed(draft_id, str(e))
        result = "failed"
    _refresh(client, draft_id)
    return result


def on_discard(client, draft_id: int, actor: str) -> str:
    if not is_allowed(actor):
        approvals.audit(actor, "discard_denied", f"#{draft_id}: user not allowed")
        return "not_allowed"
    if not approvals.decide(draft_id, "discarded", actor):
        return "already_handled"
    _refresh(client, draft_id)
    return "discarded"


def on_edit_submit(client, draft_id: int, actor: str, new_body: str) -> str:
    if not is_allowed(actor):
        approvals.audit(actor, "edit_denied", f"#{draft_id}: user not allowed")
        return "not_allowed"
    if not approvals.edit(draft_id, new_body, actor):
        return "not_editable"
    _refresh(client, draft_id)
    return "edited"


def edit_modal(draft: dict) -> dict:
    return {
        "type": "modal", "callback_id": EDIT_MODAL, "private_metadata": str(draft["id"]),
        "title": {"type": "plain_text", "text": "Edit draft post"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [{"type": "input", "block_id": "body_block",
                    "label": {"type": "plain_text", "text": "Post text"},
                    "element": {"type": "plain_text_input", "action_id": "body_input",
                                "multiline": True, "initial_value": draft["body"]}}],
    }


def run() -> None:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(token=os.getenv("APPROVAL_BOT_TOKEN") or os.getenv("SLACK_BOT_TOKEN"))

    @app.action(APPROVE)
    def _approve(ack, body, client):
        ack()
        on_approve(client, int(body["actions"][0]["value"]), body["user"]["id"])

    @app.action(DISCARD)
    def _discard(ack, body, client):
        ack()
        on_discard(client, int(body["actions"][0]["value"]), body["user"]["id"])

    @app.action(EDIT)
    def _edit(ack, body, client):
        ack()
        if not is_allowed(body["user"]["id"]):
            return
        d = approvals.get(int(body["actions"][0]["value"]))
        if d and d["status"] == "pending":
            client.views_open(trigger_id=body["trigger_id"], view=edit_modal(d))

    @app.view(EDIT_MODAL)
    def _edit_submit(ack, body, client, view):
        ack()
        text = view["state"]["values"]["body_block"]["body_input"]["value"]
        on_edit_submit(client, int(view["private_metadata"]), body["user"]["id"], text)

    token = os.getenv("APPROVAL_APP_TOKEN") or os.getenv("SLACK_APP_TOKEN")
    print("Approval listener running. Ctrl+C to stop.")
    SocketModeHandler(app, token).start()


if __name__ == "__main__":
    run()
