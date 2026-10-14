"""CLI entry point for the copilot.

Usage:
    python -m copilot.cli hello
    python -m copilot.cli build "Linear Regression" -c "use Titanic"
    python -m copilot.cli ingest --seed          # extract memory from demo/seed_messages.json
    python -m copilot.cli ingest --slack         # extract memory from the live channel
    python -m copilot.cli plan --today 2026-10-17
    python -m copilot.cli memory
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from copilot.llm import NANO, SUPER, chat


def cmd_hello(args: argparse.Namespace) -> None:
    for model_id, label in [(NANO, "Nano 30b"), (SUPER, "Super 120b")]:
        print(f"--- {label} ---")
        try:
            print(chat("In one sentence, what makes a great lecture notebook?",
                       model=model_id, max_tokens=128))
        except Exception as e:
            print(f"ERROR: {e}")
        print()


def cmd_build(args: argparse.Namespace) -> None:
    from copilot import planner
    from copilot.notebook.generate import build_notebook
    from copilot.notebook.validate import validate_and_repair

    model = None if not args.nano else NANO  # None = auto-route
    constraints = args.constraints or ""
    if args.use_memory:
        remembered = planner.build_constraints(args.topic)
        print(f"Memory constraints: {remembered or 'none'}")
        constraints = "; ".join(x for x in (constraints, remembered) if x)

    path = build_notebook(topic=args.topic, constraints=constraints,
                          model=model, output_dir=args.output_dir)
    if args.validate:
        result = validate_and_repair(path, model=model or SUPER)
        print(f"\n{'SUCCESS' if result['ok'] else 'WARNING'}: {path}")
        for e in result["errors"]:
            print(f"  Cell {e['cell_index']}: {e['error']}")
    else:
        print(f"\nNotebook saved (validation skipped): {path}")


def cmd_validate(args: argparse.Namespace) -> None:
    from copilot.notebook.validate import validate_and_repair

    result = validate_and_repair(args.path, model=NANO if args.nano else SUPER)
    print(f"\n{'PASS' if result['ok'] else 'FAIL'}: {args.path}")
    for e in result["errors"]:
        print(f"  Cell {e['cell_index']}: {e['error']}")
    sys.exit(0 if result["ok"] else 1)


def cmd_ingest(args: argparse.Namespace) -> None:
    from copilot import memory, slack_reader

    messages = slack_reader.load_seed() if args.seed else slack_reader.fetch_channel_history()
    print(f"{len(messages)} messages")
    if args.reset:
        memory.reset()
    n = slack_reader.ingest(messages, model=SUPER if args.super else NANO)
    print(f"\nStored {n} item(s). Run: python -m copilot.cli plan")


def cmd_plan(args: argparse.Namespace) -> None:
    from copilot import planner

    today = date.fromisoformat(args.today) if args.today else date.today()
    print(planner.generate_plan(today))


def cmd_memory(args: argparse.Namespace) -> None:
    from copilot import memory

    for status in ("active", "done", "cancelled", "superseded"):
        for d in memory.list_deadlines(status):
            print(f"deadline [{status}] {d['due_date']} {d['topic']} ({d['owner']})")
    for kind in ("decision", "feedback"):
        for i in memory.list_items(kind):
            print(f"{kind} [{i['topic']}] {i['summary']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="copilot", description="Content Dev Copilot CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("hello", help="Token Factory connectivity check")

    b = sub.add_parser("build", help="Generate a lecture notebook")
    b.add_argument("topic")
    b.add_argument("--constraints", "-c")
    b.add_argument("--output-dir", "-o", default="outputs")
    b.add_argument("--nano", action="store_true", help="Use Nano everywhere")
    b.add_argument("--validate", action="store_true", help="Execute notebook after building")
    b.add_argument("--use-memory", action="store_true",
                   help="Add remembered decisions and feedback to the constraints")

    v = sub.add_parser("validate", help="Execute and repair a notebook")
    v.add_argument("path")
    v.add_argument("--nano", action="store_true")

    i = sub.add_parser("ingest", help="Extract deadlines, decisions, feedback into memory")
    src = i.add_mutually_exclusive_group(required=True)
    src.add_argument("--seed", action="store_true", help="Read demo/seed_messages.json")
    src.add_argument("--slack", action="store_true", help="Read the live Slack channel")
    i.add_argument("--reset", action="store_true", help="Clear memory first")
    i.add_argument("--super", action="store_true", help="Use Super instead of Nano")

    p = sub.add_parser("plan", help="Print the daily plan")
    p.add_argument("--today", help="YYYY-MM-DD, defaults to today")

    sub.add_parser("memory", help="Dump stored memory")

    args = parser.parse_args()
    {"hello": cmd_hello, "build": cmd_build, "validate": cmd_validate,
     "ingest": cmd_ingest, "plan": cmd_plan, "memory": cmd_memory}[args.command](args)


if __name__ == "__main__":
    main()
