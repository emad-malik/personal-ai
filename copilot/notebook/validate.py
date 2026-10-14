"""Notebook validation and repair using nbclient.

Stage 1: execute generated notebooks, capture failures, attempt one repair pass.
"""

from __future__ import annotations

import json
import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

from copilot.llm import chat, SUPER


def execute_notebook(path: str, timeout: int = 120) -> dict:
    """Execute a notebook and return results.

    Returns {"ok": bool, "errors": list[dict], "path": str}
    Each error: {"cell_index": int, "source": str, "error": str}
    """
    with open(path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        allow_errors=True,
    )

    try:
        client.execute()
    except Exception as e:
        return {
            "ok": False,
            "errors": [{"cell_index": -1, "source": "", "error": str(e)}],
            "path": path,
        }

    # Check each code cell for errors
    errors = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                errors.append({
                    "cell_index": i,
                    "source": cell.source,
                    "error": f"{output.get('ename', '')}: {output.get('evalue', '')}",
                    "traceback": "\n".join(output.get("traceback", [])),
                })

    return {"ok": len(errors) == 0, "errors": errors, "path": path}


def repair_cell(source: str, error: str, model: str = SUPER) -> str:
    """Ask the LLM to fix a broken code cell."""
    prompt = f"""This Python code cell from a Jupyter notebook failed with an error.

CODE:
```python
{source}
```

ERROR:
{error}

Fix the code so it runs without errors. Keep the same intent and logic.
Use only standard libraries, scikit-learn, or other common data science packages.
Return ONLY the corrected Python code, no markdown fences, no explanation."""

    fixed = chat(prompt, model=model, temperature=0.2, max_tokens=2048)
    # Strip markdown fences if the model wraps them
    text = fixed.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def validate_and_repair(path: str, model: str = SUPER) -> dict:
    """Execute a notebook. If cells fail, attempt one repair pass.

    Returns {"ok": bool, "errors": list, "repaired": int, "path": str}
    """
    print(f"Validating: {path}")
    result = execute_notebook(path)

    if result["ok"]:
        print("  All cells passed.")
        return {**result, "repaired": 0}

    print(f"  {len(result['errors'])} cell(s) failed. Attempting repair...")

    with open(path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    repaired_count = 0

    for err in result["errors"]:
        idx = err["cell_index"]
        if idx < 0:
            continue  # Kernel-level error, can't fix a single cell

        print(f"  Repairing cell {idx}: {err['error'][:80]}")
        fixed_source = repair_cell(err["source"], err["error"], model=model)
        nb.cells[idx].source = fixed_source
        repaired_count += 1

    # Save repaired notebook
    with open(path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    # Re-execute
    print("  Re-executing after repairs...")
    result2 = execute_notebook(path)
    result2["repaired"] = repaired_count

    if result2["ok"]:
        print("  All cells passed after repair.")
    else:
        print(f"  {len(result2['errors'])} cell(s) still failing after repair.")

    return result2


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "outputs/linear_regression.ipynb"
    result = validate_and_repair(path)
    print(f"\nResult: {'PASS' if result['ok'] else 'FAIL'}")
    if not result["ok"]:
        for e in result["errors"]:
            print(f"  Cell {e['cell_index']}: {e['error']}")
