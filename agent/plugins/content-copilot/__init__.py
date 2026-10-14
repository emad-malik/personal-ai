"""Hermes plugin entry point: registers the copilot_* tools and the guard hooks."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from . import core
except ImportError:  # loaded without package context
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import core  # type: ignore


def register(ctx):
    handlers = core.make_handlers()
    for name, schema in core.SCHEMAS.items():
        ctx.register_tool(name=name, toolset="content_copilot", schema=schema,
                          handler=handlers[name])
    ctx.register_hook("pre_tool_call", core.pre_tool_call)
    ctx.register_hook("post_tool_call", core.post_tool_call)
