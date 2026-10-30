# homelab-mcp

An MCP server that lets an AI client (Claude Desktop or any MCP client) check
on a home server: container status, logs, disk, Jellyfin and Minecraft.
Read-only by default; anything that changes state is gated.

Status: **Phase 1** (hello-world server, two harmless tools). Built on the
official Python SDK, `mcp` 2.x (`MCPServer`, not the 1.x `FastMCP`).

## Run it

```bash
python -m venv .venv
.venv/Scripts/activate          # Linux: source .venv/bin/activate
pip install -e . pytest
pytest
npx @modelcontextprotocol/inspector python -m homelab_mcp.server
```

## Tools

| Tool | Tier | Phase | Status |
|------|------|-------|--------|
| `ping`, `server_info` | read-only | 1 | done |
| `container_status`, `tail_logs` (line cap), `disk_usage` | read-only | 2 | planned |
| `jellyfin_library_stats`, `minecraft_status` | read-only | 3 | planned |
| `restart_container` (allowlist + confirmation) | write | 4 | planned |

## Phases

1. Hello-world server and one client connected (MCP Inspector)
2. Docker read-only tools
3. Jellyfin and Minecraft tools
4. Gated `restart_container` and the audit log
5. This README: threat model, architecture diagram, prompt-injection demo

## Reaching the server

Start with stdio launched over SSH from the client config, which reuses
existing SSH access. HTTP transport behind Tailscale is the alternative.
Confirm SSH works with the chosen client before committing to it.

## Threat model (to fill in during Phases 4-5)

- **Docker socket = root on the host.** Anything that can talk to it can
  start privileged containers. Document the exact access given and keep it
  as narrow as possible.
- **Prompt injection through tool output.** Minecraft logs contain player
  chat, so anyone who can join can write text that looks like instructions.
  Mitigations: cap and label log output as data, never run a destructive
  tool without confirmation, demo the attack and the defence.
- **Secrets.** API keys come from environment variables, never code or
  logs. Redact logs before they leave the server.
- **Audit log.** Every tool call is recorded with a timestamp.
- **Write tools.** `restart_container` works only on an explicit allowlist
  and only after confirmation.
