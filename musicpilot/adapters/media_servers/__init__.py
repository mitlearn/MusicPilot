from __future__ import annotations

from typing import Any

from musicpilot.adapters.media_servers.navidrome import NavidromeMediaServerClient
from musicpilot.ports.media_server import MediaServerClient


def build_media_server_client(config: Any) -> MediaServerClient:
    server_type = str(getattr(config, "type", "") or "navidrome")
    if server_type == "navidrome":
        return NavidromeMediaServerClient(
            str(getattr(config, "base_url", "")),
            api_key=str(getattr(config, "api_key", "") or ""),
            username=str(getattr(config, "username", "") or ""),
            password=str(getattr(config, "password", "") or ""),
        )
    raise ValueError(f"Unsupported media server type: {server_type}")


__all__ = ["NavidromeMediaServerClient", "build_media_server_client"]
