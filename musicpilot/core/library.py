from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from musicpilot.ports.metadata import TrackMetadata

INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
AUDIO_EXTENSIONS = frozenset(
    {
        ".aac",
        ".aiff",
        ".alac",
        ".ape",
        ".dsf",
        ".flac",
        ".m4a",
        ".mp3",
        ".ogg",
        ".opus",
        ".wav",
        ".wv",
    }
)


def safe_component(value: str | None, fallback: str) -> str:
    cleaned = INVALID_PATH_CHARS.sub("_", value or "").strip().strip(".")
    return cleaned or fallback


def build_library_path(root: Path, metadata: TrackMetadata, source_path: Path) -> Path:
    artist = safe_component(metadata.artist, "Unknown Artist")
    album = safe_component(metadata.album, "Unknown Album")
    if metadata.year is not None:
        album = f"{album} ({metadata.year})"

    track_prefix = f"{metadata.track_number:02d} - " if metadata.track_number else ""
    title = safe_component(metadata.title, source_path.stem)
    extension = source_path.suffix.lower()
    return root / artist / album / f"{track_prefix}{title}{extension}"


async def hardlink_to_library(source_path: Path, target_path: Path) -> Path:
    await asyncio.to_thread(_hardlink_to_library_sync, source_path, target_path)
    return target_path


def _hardlink_to_library_sync(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        return
    os.link(source_path, target_path)


async def discover_audio_files(path: Path) -> tuple[Path, ...]:
    return await asyncio.to_thread(_discover_audio_files_sync, path)


def _discover_audio_files_sync(path: Path) -> tuple[Path, ...]:
    if path.is_file():
        return (path,) if path.suffix.lower() in AUDIO_EXTENSIONS else ()
    if not path.exists():
        return ()
    return tuple(
        sorted(
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS
        )
    )
