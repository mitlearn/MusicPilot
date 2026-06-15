from pathlib import Path

from musicpilot.core.events import DownloadCompletedEvent
from musicpilot.core.metadata import MetadataCascade
from musicpilot.core.processor import MediaProcessor
from musicpilot.ports.metadata import TrackMetadata


class FakeProvider:
    name = "fake"

    async def lookup(self, *, title: str, artist: str | None = None) -> TrackMetadata:
        del artist
        return TrackMetadata(
            title=title,
            artist="Artist",
            album="Album",
            year=2026,
            track_number=1,
        )


async def test_media_processor_hardlinks_audio_files_to_library(tmp_path: Path) -> None:
    source_dir = tmp_path / "download"
    library_dir = tmp_path / "library"
    source_dir.mkdir()
    source = source_dir / "Song.flac"
    source.write_bytes(b"not real audio")
    processor = MediaProcessor(
        library_root=library_dir,
        metadata=MetadataCascade([FakeProvider()]),
    )

    items = await processor.process_download(DownloadCompletedEvent("hash", source_dir))

    assert len(items) == 1
    assert items[0].library_path == library_dir / "Artist/Album (2026)/01 - Song.flac"
    assert items[0].library_path.exists()
