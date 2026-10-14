---
name: channel-update
description: Draft a status update or any message for the team channel and get the person's approval before it is posted. Use for "post a status update", "tell the channel ...", "draft the Friday update".
version: 0.2.0
---

# Channel Update

You are never allowed to post to the team channel on your own. You draft, then the
person decides with Approve, Edit or Discard buttons. Only an Approve answer from
the person in this conversation lets you post.

## When to Use
- "draft the status update", "post the weekly update", "send an update to the channel"
- "tell the channel that <something>"

## Procedure
1. Refresh memory: `cd ~/code/personal-ai && uv run python -m copilot.cli ingest --slack --reset`
2. Create the draft (this posts nothing):
   - Weekly status from memory: `cd ~/code/personal-ai && uv run python -m copilot.cli draft-status`
   - A message the person dictated: `cd ~/code/personal-ai && uv run python -m copilot.cli draft-post "<exact text>"`
   Note the draft number N and the draft text it prints.
3. Ask the person with a multiple-choice question (the clarify tool) so Slack shows
   buttons. Include the full draft text and the number N in the question, and give
   exactly three options: "Approve", "Edit", "Discard".
4. Act only on their answer:
   - Approve: `cd ~/code/personal-ai && uv run python -m copilot.cli approve N`
   - Discard: `cd ~/code/personal-ai && uv run python -m copilot.cli discard N`
   - Edit: ask what to change (or take the text they typed), run
     `cd ~/code/personal-ai && uv run python -m copilot.cli edit N "<new text>"`, then
     go back to step 3 with the new text. An edit never posts anything.
5. Confirm in one sentence what happened, using the command's printed result.

## Rules
- Never run `approve` in the same turn that created the draft, and never without a
  fresh Approve answer for that draft number.
- If the person does not answer, leave the draft pending. Do not post.
- Never send text to the channel any other way: not the Slack API, not `hermes send`,
  not the file uploader.
- Do not reword a message the person dictated.

## Verification
The draft command printed "Draft #N queued", and `approve` printed "posted" only after
an Approve answer.
