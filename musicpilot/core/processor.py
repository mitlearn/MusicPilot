from __future__ import annotations

import logging
from pathlib import Path

from musicpilot.core.events import DownloadCompletedEvent, ProcessedMedia
from musicpilot.core.library import build_library_path, discover_audio_files, hardlink_to_library
from musicpilot.core.metadata import MetadataCascade
from musicpilot.ports.downloader import Downloader
from musicpilot.ports.metadata import TrackMetadata
from musicpilot.ports.repository import MediaRepository
from musicpilot.ports.tag_writer import TagWriter

logger = logging.getLogger(__name__)


class MediaProcessor:
    def __init__(
        self,
        *,
        library_root: Path,
        metadata: MetadataCascade,
        downloader: Downloader | None = None,
        repository: MediaRepository | None = None,
        tag_writer: TagWriter | None = None,
    ) -> None:
        self.library_root = library_root
        self.metadata = metadata
        self.downloader = downloader
        self.repository = repository
        self.tag_writer = tag_writer

    async def process_download(self, event: DownloadCompletedEvent) -> tuple[ProcessedMedia, ...]:
        download_path = await self._resolve_download_path(event)
        if download_path is None:
            logger.warning("Unable to resolve download path for torrent %s", event.torrent_hash)
            return ()

        logger.info("Discovering audio files under %s", download_path)
        audio_files = await discover_audio_files(download_path)
        logger.info("Discovered %s audio file(s) for %s", len(audio_files), event.torrent_hash)
        if self.repository is not None:
            await self.repository.mark_torrent_completed(
                torrent_hash=event.torrent_hash,
                save_path=download_path,
            )

        processed: list[ProcessedMedia] = []
        for source_path in audio_files:
            fallback = TrackMetadata(title=source_path.stem)
            metadata = await self.metadata.lookup(title=source_path.stem) or fallback
            library_path = build_library_path(self.library_root, metadata, source_path)
            library_path = await hardlink_to_library(source_path, library_path)
            logger.info("Linked media file %s to %s", source_path, library_path)

            if self.tag_writer is not None:
                await self.tag_writer.write(library_path, metadata)

            if self.repository is not None:
                await self.repository.record_processed_media(
                    torrent_hash=event.torrent_hash,
                    source_path=source_path,
                    library_path=library_path,
                    metadata=metadata,
                )

            processed.append(
                ProcessedMedia(
                    source_path=source_path,
                    library_path=library_path,
                    title=metadata.title,
                    artist=metadata.artist,
                    album=metadata.album,
                    year=metadata.year,
                    track_number=metadata.track_number,
                )
            )

        return tuple(processed)

    async def _resolve_download_path(self, event: DownloadCompletedEvent) -> Path | None:
        if event.download_path is not None:
            return event.download_path
        if self.downloader is None:
            logger.warning("Unable to resolve download path because downloader is not configured")
            return None
        status = await self.downloader.get_status(event.torrent_hash)
        return status.save_path
