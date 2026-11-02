import asyncio
import json

import pytest

from homelab_mcp.audit import audited
from homelab_mcp.server import mcp


def _records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_tool_call_is_logged(audit_log):
    asyncio.run(mcp.call_tool("ping", {}))
    events = [(r["tool"], r["event"]) for r in _records(audit_log)]
    assert events == [("ping", "call"), ("ping", "ok")]
    assert "time" in _records(audit_log)[0]


def test_arguments_and_errors_are_logged(audit_log):
    @audited("demo")
    def demo(container, lines=1):
        raise ValueError("boom")

    with pytest.raises(ValueError):
        demo("web", lines=5)
    call, err = _records(audit_log)
    assert call["arguments"] == {"lines": "5", "arg0": "web"}
    assert err["event"] == "error" and err["error"] == "ValueError"


def test_call_refused_if_log_unwritable(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("HOMELAB_MCP_AUDIT_LOG", str(blocker / "sub" / "audit.log"))
    ran = []

    @audited("demo")
    def demo():
        ran.append(1)

    with pytest.raises(OSError):
        demo()
    assert ran == []


def test_long_arguments_are_truncated(audit_log):
    @audited("demo")
    def demo(x):
        pass

    demo("a" * 5000)
    assert len(_records(audit_log)[0]["arguments"]["arg0"]) < 300


def test_token_arguments_are_not_logged(audit_log):
    @audited("demo")
    def demo(container, confirm_token=None):
        pass

    demo("web", confirm_token="s3cret-token")
    assert "s3cret-token" not in audit_log.read_text()
    assert _records(audit_log)[0]["arguments"]["confirm_token"] == "[REDACTED]"
