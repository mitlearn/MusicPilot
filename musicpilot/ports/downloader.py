from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class DownloadState(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DownloadStatus:
    torrent_hash: str
    name: str
    state: DownloadState
    progress: float
    save_path: Path | None = None


class Downloader(Protocol):
    @property
    def name(self) -> str: ...

    async def add_torrent(self, torrent_url: str, *, category: str) -> str: ...

    async def add_torrent_file(
        self,
        torrent_data: bytes,
        *,
        filename: str,
        category: str,
    ) -> str: ...

    async def get_status(self, torrent_hash: str) -> DownloadStatus: ...
