from pathlib import Path

from musicpilot.core.library import build_library_path, safe_component
from musicpilot.ports.metadata import TrackMetadata


def test_safe_component_replaces_path_separators() -> None:
    assert safe_component("A/B:C", "fallback") == "A_B_C"


def test_build_library_path_uses_artist_album_year_and_track_number() -> None:
    metadata = TrackMetadata(
        title="Hyperballad",
        artist="Bjork",
        album="Post",
        year=1995,
        track_number=2,
    )

    path = build_library_path(Path("/music"), metadata, Path("/downloads/source.FLAC"))

    assert path == Path("/music/Bjork/Post (1995)/02 - Hyperballad.flac")
