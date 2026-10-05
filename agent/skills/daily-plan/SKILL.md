# Daily Plan

Generate a prioritized daily content development plan based on Slack channel
context, deadlines, and pending tasks.

## Trigger
- Scheduled: every morning at 8:00 AM
- On demand: user asks for today's plan

## Steps
1. Query memory for open tasks and upcoming deadlines.
2. Check Slack for overnight messages.
3. Prioritize by deadline proximity and dependencies.
4. Output a numbered plan with estimated effort per item.
