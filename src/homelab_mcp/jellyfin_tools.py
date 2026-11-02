"""Read-only Jellyfin tool: library counts and active playback sessions.

Only numbers are returned. Titles, usernames and other free text from Jellyfin
are deliberately left out so third-party text never reaches the model.
URL and API key come from JELLYFIN_URL / JELLYFIN_API_KEY.
"""

import json
import os
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from homelab_mcp.audit import audited

MAX_RESPONSE_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 5

_COUNT_FIELDS = {
    "movies": "MovieCount",
    "series": "SeriesCount",
    "episodes": "EpisodeCount",
    "songs": "SongCount",
    "albums": "AlbumCount",
    "artists": "ArtistCount",
    "books": "BookCount",
}


def _config() -> tuple[str, str]:
    base = os.environ.get("JELLYFIN_URL", "http://localhost:8096").rstrip("/")
    if urlsplit(base).scheme not in ("http", "https"):
        raise RuntimeError("JELLYFIN_URL must start with http:// or https://")
    key = os.environ.get("JELLYFIN_API_KEY")
    if not key:
        raise RuntimeError("JELLYFIN_API_KEY is not set")
    return base, key


def _http_get_json(url: str, api_key: str):
    req = Request(url, headers={"X-Emby-Token": api_key, "Accept": "application/json"})
    with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # noqa: S310 (scheme checked)
        return json.loads(resp.read(MAX_RESPONSE_BYTES))


def library_stats(get_json: Callable[[str, str], object] = _http_get_json) -> dict:
    base, key = _config()
    counts = get_json(f"{base}/Items/Counts", key)
    sessions = get_json(f"{base}/Sessions?activeWithinSeconds=960", key)
    return {
        **{name: int(counts.get(field) or 0) for name, field in _COUNT_FIELDS.items()},
        "active_sessions": len(sessions),
        "playing_now": sum(1 for s in sessions if s.get("NowPlayingItem")),
    }


def register(mcp, annotations, get_json: Callable[[str, str], object] = _http_get_json) -> None:
    @mcp.tool(name="jellyfin_library_stats", annotations=annotations)
    @audited("jellyfin_library_stats")
    def jellyfin_library_stats() -> dict:
        """Jellyfin library counts (movies, series, episodes, songs, albums,
        artists, books) plus how many sessions are active and how many are
        playing something right now. Numbers only."""
        return library_stats(get_json)
