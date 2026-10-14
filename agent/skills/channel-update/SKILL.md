---
name: channel-update
description: Draft a status update or any message for the team channel and get the person's approval before it is posted. Use for "post a status update", "tell the channel ...", "draft the Friday update".
version: 0.3.0
---

# Channel Update

You never post to the team channel on your own. Use the copilot_* tools only.

## Procedure
1. Do not ask the person questions first. Do not call `copilot_refresh_memory` unless the person asks to refresh or says new messages arrived.
2. Weekly status: `copilot_draft_status` (pass `note` only if the person gave extra text,
   it is appended verbatim). Dictated message: `copilot_draft_post` with their exact text.
3. Follow the tool's `next_step`: one `clarify` question containing "Draft #N" and the
   full draft text, choices exactly Approve, Edit, Discard.
4. Act on the answer:
   - Approve: `copilot_approve` with draft_id N
   - Discard: `copilot_discard`
   - Edit: take the person's new text, `copilot_edit`, then clarify again.
5. Confirm in one sentence using the tool result.

## Rules
- `copilot_approve` is refused unless the person just pressed Approve. Do not try shell or Slack workarounds, they are blocked.
- If they skip a part (for example next steps), do not add it back.
- Do not reword dictated text. Do not invent content beyond the tool's draft.
