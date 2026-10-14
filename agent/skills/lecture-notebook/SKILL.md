# Lecture Notebook Skill

Generate a Jupyter notebook for a bootcamp lecture topic that meets reviewer
standards on the first pass.

## Trigger

- User requests a notebook for a specific topic.
- Daily plan includes a notebook generation task.

## Standards

### One notebook, one topic, one day

Each notebook covers a single topic that fits in one teaching day. If a topic
is too broad, split it. Filename is the topic itself, no LECTURE/LAB/DEMO tags.

### Structure (in this order)

1. **Header** -- core concepts, tools, models covered.
2. **Dataset introduction** -- only if the dataset is new to the course.
3. **Core content** -- explanation-then-code, topic by topic.
4. **Exercise** -- 10-15 minutes, applying what was just taught.
5. **Conclusion** -- practical, industry-facing summary.
6. **Resources** -- 2-4 annotated links as the final cell.

### Code cells

- Every new function/technique gets a markdown explanation before it.
- Split cells by concept boundary, not line count.
- Pipeline calls to already-explained functions don't need re-explanation.

### Markdown style

- No em dashes or en dashes. Use periods, commas, or restructure.
- No filler ("it's worth noting," "as we can see").
- Every sentence teaches something. If it can be deleted without losing
  information, delete it.

### Exercise

- One exercise, 10-15 minutes, concrete and checkable.
- No open-ended prompts. Give a specific task with a verifiable outcome.

### Conclusion

- Answer: where does this get used in practice, and why this technique
  over alternatives?
- Ground claims in current information.

## Review checklist

- [ ] One topic, one day
- [ ] No LECTURE/LAB/DEMO filename tag
- [ ] Header states concepts, tools, models
- [ ] Dataset introduced if new
- [ ] Every new concept has a markdown cell before its code
- [ ] No redundant re-explanations of already-covered functions
- [ ] Code cells split by concept boundary
- [ ] No em/en dashes, no filler in markdown
- [ ] Resources section with 2-4 annotated links
- [ ] 10-15 minute exercise, scoped and checkable
- [ ] Conclusion covers industry usage with verified claims

## Steps

1. Retrieve topic context from memory (past decisions, scope, prerequisites).
2. Generate an outline: header, dataset, sections, exercise, conclusion, resources.
3. Build the notebook cell-by-cell using nbformat.
4. Validate by executing with nbclient. One repair pass on failures.
5. Save to outputs/ and report status.
