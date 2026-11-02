# homelab-mcp

An MCP server that lets an AI client (Claude Desktop or any MCP client) check
on a home server: container status, logs, disk, Jellyfin and Minecraft.
Read-only by default; anything that changes state is gated.

Status: **Phase 3** (read-only Docker, Jellyfin and Minecraft tools, audit log). Built on the
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
| `container_status` | read-only | 2 | done: name, image, state, health, uptime |
| `tail_logs(container, lines=50)` | read-only | 2 | done: name validated, max 200 lines / ~16 KB, secrets redacted, output labelled untrusted |
| `disk_usage` | read-only | 2 | done: main filesystem plus per-container size from the Docker API |
| `jellyfin_library_stats` | read-only | 3 | done: library counts and active sessions, numbers only |
| `minecraft_status` | read-only | 3 | done: server list ping, version and player counts; MOTD dropped, names filtered |
| `restart_container` (allowlist + confirmation) | write | 4 | planned |

## Configuration (environment variables)

| Variable | Used by | Default |
|----------|---------|---------|
| `JELLYFIN_URL` | `jellyfin_library_stats` | `http://localhost:8096` |
| `JELLYFIN_API_KEY` | `jellyfin_library_stats` | none (required) |
| `MINECRAFT_HOST`, `MINECRAFT_PORT` | `minecraft_status` | `localhost`, `25565` |
| `HOMELAB_MCP_AUDIT_LOG` | audit log | `~/.homelab-mcp/audit.log` |

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
- **Audit log.** Every tool call is written as a JSON line (tool, arguments,
  time, outcome) before it runs. If the log can't be written, the call is refused.
- **Write tools.** `restart_container` works only on an explicit allowlist
  and only after confirmation.
