"""Audit log: one JSON line per tool call (tool, arguments, time, outcome).

The log path comes from HOMELAB_MCP_AUDIT_LOG (default ~/.homelab-mcp/audit.log).
If the log cannot be written the call is refused: no audit record, no tool run.
"""

import functools
import json
import os
from datetime import datetime, timezone
from pathlib import Path

_MAX_ARG_CHARS = 200


def audit_path() -> Path:
    env = os.environ.get("HOMELAB_MCP_AUDIT_LOG")
    return Path(env) if env else Path.home() / ".homelab-mcp" / "audit.log"


def _write(record: dict) -> None:
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _short(value):
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= _MAX_ARG_CHARS else text[:_MAX_ARG_CHARS] + "..."


def audited(tool_name: str):
    """Decorator: record the call before running it, then the outcome."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            record = {
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "tool": tool_name,
                "arguments": {k: _short(v) for k, v in kwargs.items()}
                | {f"arg{i}": _short(v) for i, v in enumerate(args)},
            }
            _write({**record, "event": "call"})
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                _write({**record, "event": "error", "error": type(exc).__name__})
                raise
            _write({**record, "event": "ok"})
            return result

        return wrapper

    return decorator
