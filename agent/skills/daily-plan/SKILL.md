---
name: daily-plan
description: Read the bootcamp content channel into memory and report what is due, what changed, and what to build next. Use for "what is due", "plan for today", "what changed", or a morning plan.
version: 0.1.0
---

# Daily Plan

Reports from the project's own memory. Do not work out dates yourself. The plan
command sorts deadlines and applies changes exactly.

## When to Use
- "what's due", "plan for today", "what changed since yesterday"
- a scheduled morning plan

## Procedure
1. Refresh memory from Slack:
   `cd ~/code/personal-ai && uv run python -m copilot.cli ingest --slack --reset`
2. Print the plan:
   `cd ~/code/personal-ai && uv run python -m copilot.cli plan`
3. Reply with the plan in short plain text: due list (soonest first, with owner and any
   moved dates), changes since yesterday, and the proposed build. End by asking
   whether to build the proposed notebook.

## Pitfalls
- Ingest takes a minute. Wait for it.
- Never post to the channel. Only reply to the person who asked. Channel posts need
  the approval queue (added in a later stage).

## Verification
The due list in the reply matches the "Due" section printed by the plan command.
