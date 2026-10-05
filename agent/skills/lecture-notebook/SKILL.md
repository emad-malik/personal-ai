# Lecture Notebook

Generate a Jupyter notebook for a bootcamp lecture topic.

## Trigger
- User requests a notebook for a specific topic.
- Daily plan includes a notebook generation task.

## Steps
1. Retrieve topic context from memory (past decisions, scope, prerequisites).
2. Generate an outline: learning objectives, sections, code cells, exercises.
3. Build the notebook using nbformat.
4. Validate by executing with nbclient.
5. Save to outputs/ and report status.
