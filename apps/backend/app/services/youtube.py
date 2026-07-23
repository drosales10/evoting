"""YouTube URL helpers for election ceremony broadcasts."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


class YouTubeUrlError(ValueError):
    """Raised when a URL is not an accepted YouTube watch/live/embed link."""


def extract_youtube_video_id(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise YouTubeUrlError("youtube_url is required")

    parsed = urlparse(cleaned)
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]

    video_id: str | None = None
    if host in {"youtu.be"}:
        video_id = parsed.path.lstrip("/").split("/")[0] or None
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        path = parsed.path.strip("/")
        parts = path.split("/") if path else []
        if parts and parts[0] in {"embed", "live", "shorts", "v"} and len(parts) >= 2:
            video_id = parts[1]
        else:
            query = parse_qs(parsed.query)
            video_id = (query.get("v") or [None])[0]
    else:
        raise YouTubeUrlError("Only YouTube URLs are supported")

    if not video_id or not _VIDEO_ID_RE.fullmatch(video_id):
        raise YouTubeUrlError("Could not extract a valid YouTube video id")
    return video_id


def youtube_embed_url(video_id: str) -> str:
    return f"https://www.youtube-nocookie.com/embed/{video_id}"


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
