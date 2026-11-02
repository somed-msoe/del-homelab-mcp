import asyncio

from homelab_mcp.server import mcp


def test_tools_are_registered_and_read_only():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert {"ping", "server_info"} <= names
    for t in tools:
        assert t.annotations is not None
        if t.name == "restart_container":  # the one write tool, tested in test_docker_write_tools
            assert t.annotations.read_only_hint is False and t.annotations.destructive_hint is True
        else:
            assert t.annotations.read_only_hint is True


def test_ping_returns_pong():
    result = asyncio.run(mcp.call_tool("ping", {}))
    assert "pong" in str(result)
