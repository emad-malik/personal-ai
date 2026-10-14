---
name: lecture-notebook
description: Build a bootcamp lecture notebook (.ipynb) for the next due topic or a named topic, using decisions remembered from the Slack channel. Use when asked to build, draft or generate a notebook.
version: 0.1.0
---

# Lecture Notebook

Builds a lecture notebook with the project's own generator. Do not write notebook
content yourself. The generator applies the course standards (one topic per day,
header, dataset intro, explanation before code, exercise, conclusion, resources,
no em dashes) and the remembered Slack decisions (dataset, scope, reviewer feedback).

## When to Use
- "build the next notebook" or "build the next one"
- "build a notebook on <topic>"

## Procedure
1. Refresh memory first if the user mentions new messages or it has been a while:
   `cd ~/code/personal-ai && uv run python -m copilot.cli ingest --slack --reset`
2. Next due topic:
   `cd ~/code/personal-ai && uv run python -m copilot.cli build-next`
   Named topic:
   `cd ~/code/personal-ai && uv run python -m copilot.cli build "<topic>" --use-memory`
3. The build makes about 10 model calls and takes a few minutes. Run it in the
   background and poll the process, do not give up on a slow command.
4. When it finishes, read the line starting with "Notebook file:" and the line
   "Memory constraints:". Reply with:
   - the topic and its due date,
   - which remembered decisions were applied,
   - the absolute notebook path written as plain text, not in backticks or a code
     block, so the gateway uploads the file to the chat.
5. Never paste the notebook contents into the chat.

## Pitfalls
- Run commands from ~/code/personal-ai so the .env and outputs/ folder are found.
- If the command fails, report the last error lines and stop. Do not retry in a loop.
- Add `--validate` only if the user asks for an execution check.

## Verification
The reply names a real file under ~/code/personal-ai/outputs/ and lists the
constraints that came from memory.
