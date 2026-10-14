"""Lecture notebook generator.

Stage 1: topic + constraints -> structured .ipynb via LLM + nbformat.

Model routing:
  - Nano: outline, header, markdown explanations, conclusion, resources
  - Super: code sections, exercises (need correct Python)
  - Override with an explicit model to force one everywhere.
"""

from __future__ import annotations

import json
import os

import nbformat

from copilot.llm import chat, SUPER, NANO

SYSTEM_PROMPT = """\
You are a lecture-notebook author for a data science bootcamp.

RULES (non-negotiable):
- One topic per notebook, sized for one teaching day.
- Structure: Header, Dataset intro (if new), Core content, Exercise, Conclusion, Resources.
- Header must list: core concepts, tools, models covered.
- Every new concept/function gets a markdown explanation BEFORE its code cell.
- Split code cells by concept boundary, not line count.
- Markdown style: no em dashes, no filler ("it's worth noting"), every sentence teaches.
- Exercise: one concrete task, 10-15 min, checkable outcome.
- Conclusion: where is this used in practice, why over alternatives.
- Resources: 2-4 annotated links as the final cell.
- All code must use small built-in or easily pip-installable datasets.
- All code cells must be self-contained enough to execute top-to-bottom.
- Include necessary imports at the top of the notebook.
"""

# ---- routing ---------------------------------------------------------------

_HEAVY_TYPES = {"code", "exercise"}


def _pick_model(section_type: str) -> str:
    """Nano for text, Super for code-heavy sections."""
    return SUPER if section_type in _HEAVY_TYPES else NANO


# ---- helpers ---------------------------------------------------------------

def _strip_fences(text: str) -> str:
    """Remove markdown code fences wrapping a response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def _parse_json(raw: str, fallback_title: str = "") -> dict:
    """Parse an LLM JSON response; fall back gracefully."""
    if not raw or not raw.strip():
        return {"markdown": f"## {fallback_title}" if fallback_title else "", "code": None}
    text = _strip_fences(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"markdown": text, "code": None}


# ---- outline ---------------------------------------------------------------

def _sanitize_text(text: str) -> str:
    """Replace special Unicode dashes/quotes with ASCII equivalents."""
    replacements = {
        "‑": "-",  # non-breaking hyphen
        "–": "-",  # en dash
        "—": "-",  # em dash
        "‘": "'",  # left single quote
        "’": "'",  # right single quote
        "“": '"',  # left double quote
        "”": '"',  # right double quote
        "…": "...",  # ellipsis
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text


def _cache_path(topic: str, output_dir: str = "outputs") -> str:
    """Return path for the intermediate cell cache file."""
    slug = topic.lower().replace(" ", "_").replace("/", "_")[:60]
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{slug}_cache.json")


def _save_cache(cache_path: str, data: dict) -> None:
    """Save intermediate results (outline + generated cells) to disk."""
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_cache(cache_path: str) -> dict | None:
    """Load cached intermediate results if they exist."""
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def generate_outline(topic: str, constraints: str = "", model: str = NANO) -> list[dict]:
    """Ask the LLM for a notebook outline as a JSON array of sections."""
    prompt = f"""Create a detailed outline for a lecture notebook on: {topic}

Additional constraints: {constraints if constraints else "None"}

Return a JSON array. Each element:
  "title": section heading,
  "type": one of "header", "markdown", "code", "exercise", "conclusion", "resources",
  "description": 1-2 sentences on what this section covers,
  "has_code": boolean

Return ONLY the JSON array, no other text."""

    raw = chat(prompt, model=model, system=SYSTEM_PROMPT, temperature=0.4, max_tokens=2048)
    text = _strip_fences(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse outline JSON:\n{text[:500]}")


# ---- cell content ----------------------------------------------------------

def generate_cell_content(
    topic: str,
    section: dict,
    prev_sections: list[str],
    constraints: str = "",
    model: str = SUPER,
) -> dict[str, str]:
    """Generate markdown and/or code for one section.

    Returns {"markdown": str, "code": str | None}.
    """
    context = "\n".join(prev_sections[-3:]) if prev_sections else "This is the first section."
    section_type = section["type"]
    title = section.get("title", "")
    desc = section.get("description", "")

    if section_type == "header":
        prompt = f"""Write the header cell for a lecture notebook on: {topic}

Format:
# [Descriptive Title]

**Core concepts:** [list them]

**Tools:** [list them]

**Models covered:** [list them, if applicable]

Return ONLY the markdown content."""
        md = chat(prompt, model=model, system=SYSTEM_PROMPT, temperature=0.3, max_tokens=512)
        return {"markdown": (md or "").strip() or f"# {topic}", "code": None}

    if section_type == "resources":
        prompt = f"""Write a "Further Reading" section for a notebook on: {topic}

Include 2-4 links with one-line annotations.
Use real documentation URLs (scikit-learn docs, official papers, etc.).
Start with ## Further Reading.

Return ONLY the markdown."""
        md = chat(prompt, model=model, system=SYSTEM_PROMPT, temperature=0.3, max_tokens=512)
        return {"markdown": (md or "").strip() or "## Further Reading", "code": None}

    if section_type == "exercise":
        prompt = f"""Write an exercise for a notebook on: {topic}

Section: {title}
Description: {desc}
Previous content covered: {context}
Constraints: {constraints if constraints else "None"}

Requirements:
- One concrete task, 10-15 minutes, checkable outcome
- Uses only what the notebook already covered
- Provide starter code in a code cell
- No open-ended prompts

Return as JSON: {{"markdown": "## Exercise\\n...", "code": "# Exercise: ...\\n..."}}
Return ONLY the JSON."""
        raw = chat(prompt, model=model, system=SYSTEM_PROMPT, temperature=0.4, max_tokens=1024)
        return _parse_json(raw, title)

    if section_type == "conclusion":
        prompt = f"""Write a conclusion for a notebook on: {topic}

Previous content covered: {context}
Constraints: {constraints if constraints else "None"}

Requirements:
- Start with ## Conclusion
- Where is this used in practice, and why over alternatives?
- Specific industry use cases
- No em dashes, no filler

Return ONLY the markdown."""
        md = chat(prompt, model=model, system=SYSTEM_PROMPT, temperature=0.4, max_tokens=512)
        return {"markdown": (md or "").strip() or "## Conclusion", "code": None}

    # Default: markdown + optional code
    prompt = f"""Write content for this section of a notebook on: {topic}

Section title: {title}
Description: {desc}
Previous content: {context}
Constraints: {constraints if constraints else "None"}

Requirements:
- Explanation markdown: clear, no filler, no em dashes, every sentence teaches.
- If code is needed: working Python that runs top-to-bottom.
- Code must use standard libraries or scikit-learn with built-in datasets.
- Include necessary imports.

Return as JSON: {{"markdown": "## {title}\\n...", "code": "# code here\\n..." or null}}
Return ONLY the JSON."""

    raw = chat(prompt, model=model, system=SYSTEM_PROMPT, temperature=0.4, max_tokens=2048)
    return _parse_json(raw, title)


# ---- main pipeline ---------------------------------------------------------

def build_notebook(
    topic: str,
    constraints: str = "",
    model: str | None = None,
    output_dir: str = "outputs",
) -> str:
    """Full pipeline: topic -> outline -> cells -> .ipynb file.

    model=None uses auto-routing (Nano for text, Super for code).
    """
    outline_model = model or NANO
    print(f"Generating outline for: {topic} (model: {outline_model})")
    outline = generate_outline(topic, constraints, model=outline_model)
    print(f"  {len(outline)} sections planned")

    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }

    prev_sections: list[str] = []

    for i, section in enumerate(outline):
        section_model = model or _pick_model(section.get("type", "markdown"))
        label = section_model.split("/")[-1]
        print(f"  [{i+1}/{len(outline)}] {section['title']} ({label})")
        try:
            content = generate_cell_content(
                topic, section, prev_sections, constraints, model=section_model
            )
        except Exception as e:
            print(f"    WARNING: {e}")
            content = {
                "markdown": f"## {section.get('title', 'Section')}\n\n"
                            f"*Generation failed: {section.get('description', '')}*",
                "code": None,
            }

        if content.get("markdown"):
            nb.cells.append(nbformat.v4.new_markdown_cell(_sanitize_text(content["markdown"])))
            prev_sections.append(content["markdown"][:200])

        if content.get("code"):
            nb.cells.append(nbformat.v4.new_code_cell(_sanitize_text(content["code"])))
            prev_sections.append(f"[code] {content['code'][:100]}")

    os.makedirs(output_dir, exist_ok=True)
    slug = topic.lower().replace(" ", "_").replace("/", "_")[:60]
    path = os.path.join(output_dir, f"{slug}.ipynb")
    with open(path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    print(f"  Saved: {path}")
    return path


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "Linear Regression"
    constraints = sys.argv[2] if len(sys.argv) > 2 else ""
    path = build_notebook(topic, constraints)
    print(f"\nNotebook saved to: {path}")
