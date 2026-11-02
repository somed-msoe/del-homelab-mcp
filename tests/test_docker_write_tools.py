import asyncio

import pytest
from docker.errors import NotFound

from homelab_mcp import docker_write_tools as w
from homelab_mcp.server import mcp


class Box:
    def __init__(self, name):
        self.name = name
        self.restarts = []

    def restart(self, timeout):
        self.restarts.append(timeout)


class FakeClient:
    def __init__(self, *names):
        self.boxes = {n: Box(n) for n in names}
        self.containers = self

    def get(self, name):
        if name not in self.boxes:
            raise NotFound("x")
        return self.boxes[name]


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.delenv("HOMELAB_MCP_RESTART_ALLOWLIST", raising=False)
    client = FakeClient("jellyfin", "komga", "gitea", "minecraft")
    clock = Clock()
    return w.Restarter(lambda: client, clock), client, clock


def test_registered_as_write_tool():
    tool = {t.name: t for t in asyncio.run(mcp.list_tools())}["restart_container"]
    assert tool.annotations.read_only_hint is False
    assert tool.annotations.destructive_hint is True


@pytest.mark.parametrize("target", ["gitea", "minecraft", "grafana"])
def test_refuses_non_allowlisted_targets(setup, target):
    r, client, _ = setup
    with pytest.raises(ValueError, match="allowlist"):
        r.restart(target)
    with pytest.raises(ValueError, match="allowlist"):
        r.restart(target, confirm_token="whatever")
    assert all(not b.restarts for b in client.boxes.values())


def test_rejects_bad_names(setup):
    r, _, _ = setup
    for bad in ("../x", "jellyfin;id", "", "jellyfin\n"):
        with pytest.raises(ValueError):
            r.restart(bad)


def test_first_call_restarts_nothing(setup):
    r, client, _ = setup
    out = r.restart("jellyfin")
    assert out["restarted"] is False and out["confirm_token"]
    assert client.boxes["jellyfin"].restarts == []


def test_second_call_with_token_restarts_once(setup):
    r, client, _ = setup
    token = r.restart("jellyfin")["confirm_token"]
    assert r.restart("jellyfin", token) == {"restarted": True, "container": "jellyfin"}
    assert client.boxes["jellyfin"].restarts == [w.RESTART_TIMEOUT_SECONDS]
    with pytest.raises(ValueError, match="token"):
        r.restart("jellyfin", token)  # single use
    assert len(client.boxes["jellyfin"].restarts) == 1


def test_token_is_bound_to_container(setup):
    r, client, _ = setup
    token = r.restart("jellyfin")["confirm_token"]
    with pytest.raises(ValueError, match="token"):
        r.restart("komga", token)
    with pytest.raises(ValueError, match="token"):
        r.restart("jellyfin", token)  # burned by the wrong-target attempt
    assert all(not b.restarts for b in client.boxes.values())


def test_token_expires(setup):
    r, client, clock = setup
    token = r.restart("jellyfin")["confirm_token"]
    clock.t += w.TOKEN_TTL_SECONDS + 1
    with pytest.raises(ValueError, match="token"):
        r.restart("jellyfin", token)
    assert client.boxes["jellyfin"].restarts == []


def test_made_up_token_rejected(setup):
    r, client, _ = setup
    with pytest.raises(ValueError, match="token"):
        r.restart("jellyfin", "guess")
    assert client.boxes["jellyfin"].restarts == []


def test_unknown_container_on_allowlist(setup, monkeypatch):
    r, _, _ = setup
    monkeypatch.setenv("HOMELAB_MCP_RESTART_ALLOWLIST", "navidrome")
    with pytest.raises(ValueError, match="No such container"):
        r.restart("navidrome")


def test_pending_tokens_capped(setup):
    r, _, _ = setup
    for _ in range(w.MAX_PENDING):
        r.restart("jellyfin")
    with pytest.raises(ValueError, match="Too many"):
        r.restart("jellyfin")


def test_allowlist_env_override_and_validation(monkeypatch):
    monkeypatch.setenv("HOMELAB_MCP_RESTART_ALLOWLIST", "a, b")
    assert w.allowlist() == {"a", "b"}
    monkeypatch.setenv("HOMELAB_MCP_RESTART_ALLOWLIST", "ok,../bad")
    with pytest.raises(ValueError):
        w.allowlist()


def test_refusal_reason_reaches_the_model_through_the_sdk(monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    monkeypatch.delenv("HOMELAB_MCP_RESTART_ALLOWLIST", raising=False)
    with pytest.raises(ToolError, match="not on the restart allowlist"):
        asyncio.run(mcp.call_tool("restart_container", {"container": "gitea"}))
    with pytest.raises(ToolError, match="Invalid container name"):
        asyncio.run(mcp.call_tool("tail_logs", {"container": "../etc"}))
