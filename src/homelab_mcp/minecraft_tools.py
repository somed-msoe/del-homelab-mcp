"""Read-only Minecraft tool using the Server List Ping (no RCON, no secrets).

Host/port come from MINECRAFT_HOST / MINECRAFT_PORT, never from tool input.
The MOTD and any other free text are dropped. Player names are only returned
if they match Minecraft's own name rule, so chat-style text can't ride along.
"""

import json
import os
import re
import socket
import struct

from homelab_mcp.audit import audited

TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 64 * 1024
MAX_PLAYER_NAMES = 20
_NAME_RE = re.compile(r"[A-Za-z0-9_]{1,16}")


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed early")
        buf += chunk
    return bytes(buf)


def _read_varint(sock: socket.socket) -> int:
    result = 0
    for shift in range(0, 35, 7):
        byte = _read_exact(sock, 1)[0]
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result
    raise ValueError("varint too long")


def ping(host: str, port: int) -> dict:
    with socket.create_connection((host, port), timeout=TIMEOUT_SECONDS) as sock:
        sock.settimeout(TIMEOUT_SECONDS)
        hostb = host.encode("utf-8")
        handshake = b"\x00" + _varint(-1 & 0xFFFFFFFF) + _varint(len(hostb)) + hostb
        handshake += struct.pack(">H", port) + b"\x01"
        sock.sendall(_varint(len(handshake)) + handshake)
        sock.sendall(b"\x01\x00")  # status request

        length = _read_varint(sock)
        if not 0 < length <= MAX_RESPONSE_BYTES:
            raise ValueError("unexpected response size")
        packet = _read_exact(sock, length)

    # packet: id varint (0x00), then string length varint, then JSON
    pos = 0
    if packet[pos] != 0x00:
        raise ValueError("unexpected packet id")
    pos += 1
    strlen, shift = 0, 0
    while True:
        byte = packet[pos]
        pos += 1
        strlen |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
    return json.loads(packet[pos : pos + strlen].decode("utf-8", errors="replace"))


def minecraft_status(ping_fn=ping) -> dict:
    host = os.environ.get("MINECRAFT_HOST", "localhost")
    port = int(os.environ.get("MINECRAFT_PORT", "25565"))
    if not 0 < port < 65536:
        raise RuntimeError("MINECRAFT_PORT out of range")
    try:
        data = ping_fn(host, port)
    except (OSError, ValueError) as exc:
        return {"online": False, "error": type(exc).__name__}
    players = data.get("players") or {}
    version = str((data.get("version") or {}).get("name", ""))[:40]
    names = [
        p["name"]
        for p in (players.get("sample") or [])
        if isinstance(p, dict) and isinstance(p.get("name"), str) and _NAME_RE.fullmatch(p["name"])
    ][:MAX_PLAYER_NAMES]
    return {
        "online": True,
        "version": version,
        "players_online": int(players.get("online") or 0),
        "players_max": int(players.get("max") or 0),
        "player_names": names,
    }


def register(mcp, annotations, ping_fn=ping) -> None:
    @mcp.tool(name="minecraft_status", annotations=annotations)
    @audited("minecraft_status")
    def minecraft_status_tool() -> dict:
        """Whether the Minecraft server answers, its version, and player
        counts. Player names are included only if they are valid Minecraft
        names. The MOTD and chat are never returned."""
        return minecraft_status(ping_fn)
