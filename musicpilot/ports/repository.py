from __future__ import annotations

from pathlib import Path
from typing import Protocol

from musicpilot.ports.metadata import TrackMetadata


class MediaRepository(Protocol):
    async def record_processed_media(
        self,
        *,
        torrent_hash: str,
        source_path: Path,
        library_path: Path,
        metadata: TrackMetadata,
    ) -> None: ...

    async def mark_torrent_completed(
        self,
        *,
        torrent_hash: str,
        save_path: Path | None,
    ) -> None: ...
