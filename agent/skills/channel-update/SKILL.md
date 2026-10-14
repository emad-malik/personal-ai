---
name: channel-update
description: Draft a status update or any message for the team channel. Drafts only go to the approval queue, the person approves before anything is posted. Use for "post a status update", "tell the channel ...", "draft the Friday update".
version: 0.1.0
---

# Channel Update

You are never allowed to post to the team channel yourself. You only create a draft.
The person gets a DM with Approve, Edit and Discard buttons, and the post goes out
only after they press Approve.

## When to Use
- "draft the status update", "post the weekly update", "send an update to the channel"
- "tell the channel that <something>"

## Procedure
1. Refresh memory: `cd ~/code/personal-ai && uv run python -m copilot.cli ingest --slack --reset`
2. Weekly status (built from memory, exact dates):
   `cd ~/code/personal-ai && uv run python -m copilot.cli draft-status`
   Any other message the person dictated:
   `cd ~/code/personal-ai && uv run python -m copilot.cli draft-post "<exact text>"`
3. Reply with one sentence: the draft is in their DM waiting for approval. Do not
   claim anything was posted.

## Pitfalls
- Never use any other tool or command to send text to the channel, not the Slack API,
  not `hermes send`, not the file uploader. Channel posts go through the queue only.
- Do not reword a message the person dictated.

## Verification
The command printed "Draft #N queued (pending approval)".
