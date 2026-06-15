from __future__ import annotations

from pathlib import Path

import httpx

from musicpilot.ports.downloader import DownloadState, DownloadStatus


class QBittorrentAuthError(RuntimeError):
    pass


class QBittorrentClient:
    def __init__(
        self,
        base_url: str,
        *,
        username: str,
        password: str,
        download_path: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.download_path = download_path
        self._client = client or httpx.AsyncClient(base_url=self.base_url, timeout=20)
        self._owns_client = client is None

    @property
    def name(self) -> str:
        return "qbittorrent"

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def login(self) -> None:
        response = await self._client.post(
            "/api/v2/auth/login",
            data={"username": self.username, "password": self.password},
        )
        response.raise_for_status()
        body = response.text.strip().lower()
        if body not in {"ok.", "ok"}:
            raise QBittorrentAuthError(
                f"qBittorrent authentication failed: {response.text[:120]}"
            )

    async def test_connection(self) -> None:
        await self.login()
        response = await self._client.get("/api/v2/torrents/info")
        response.raise_for_status()

    async def add_torrent(self, torrent_url: str, *, category: str) -> str:
        await self.login()
        data = {"urls": torrent_url, "category": category, "tags": "MusicPilot"}
        save_path = getattr(self, "download_path", "")
        if save_path:
            data["savepath"] = save_path
        response = await self._client.post(
            "/api/v2/torrents/add",
            data=data,
        )
        response.raise_for_status()
        return ""

    async def get_status(self, torrent_hash: str) -> DownloadStatus:
        await self.login()
        response = await self._client.get("/api/v2/torrents/info", params={"hashes": torrent_hash})
        response.raise_for_status()
        items = response.json()
        if not items:
            return DownloadStatus(torrent_hash, "", DownloadState.FAILED, 0.0)
        item = items[0]
        progress = float(item.get("progress", 0.0))
        state = DownloadState.COMPLETED if progress >= 1 else DownloadState.DOWNLOADING
        save_path = item.get("save_path")
        return DownloadStatus(
            torrent_hash=torrent_hash,
            name=str(item.get("name", "")),
            state=state,
            progress=progress,
            save_path=Path(save_path) if save_path else None,
        )

    async def list_statuses(self) -> tuple[DownloadStatus, ...]:
        await self.login()
        response = await self._client.get("/api/v2/torrents/info")
        response.raise_for_status()
        return tuple(_status_from_item(item) for item in response.json())


def _status_from_item(item: dict[str, object]) -> DownloadStatus:
    torrent_hash = str(item.get("hash", ""))
    progress = float(item.get("progress", 0.0))
    state = DownloadState.COMPLETED if progress >= 1 else DownloadState.DOWNLOADING
    save_path = item.get("save_path")
    return DownloadStatus(
        torrent_hash=torrent_hash,
        name=str(item.get("name", "")),
        state=state,
        progress=progress,
        save_path=Path(str(save_path)) if save_path else None,
    )
