from __future__ import annotations

import asyncio
from pathlib import Path

from musicpilot.ports.metadata import TrackMetadata


class MutagenTagWriter:
    async def write(self, path: Path, metadata: TrackMetadata) -> None:
        await asyncio.to_thread(_write_tags_sync, path, metadata)


def _write_tags_sync(path: Path, metadata: TrackMetadata) -> None:
    from mutagen import File as MutagenFile

    audio = MutagenFile(path, easy=True)
    if audio is None:
        return

    try:
        if audio.tags is None:
            audio.add_tags()
    except Exception:
        return

    _set_tag(audio, "title", metadata.title)
    _set_tag(audio, "artist", metadata.artist)
    _set_tag(audio, "album", metadata.album)
    _set_tag(audio, "date", str(metadata.year) if metadata.year is not None else None)
    _set_tag(
        audio,
        "tracknumber",
        str(metadata.track_number) if metadata.track_number is not None else None,
    )
    if metadata.lyrics:
        _set_tag(audio, "lyrics", metadata.lyrics)
    audio.save()


def _set_tag(audio: object, key: str, value: str | None) -> None:
    if value:
        audio[key] = [value]
