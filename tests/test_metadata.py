from musicpilot.core.metadata import MetadataCascade
from musicpilot.ports.metadata import TrackMetadata


class EmptyProvider:
    name = "empty"

    async def lookup(self, *, title: str, artist: str | None = None) -> None:
        del title, artist
        return None


class HitProvider:
    name = "hit"

    async def lookup(self, *, title: str, artist: str | None = None) -> TrackMetadata:
        del artist
        return TrackMetadata(title=title, artist="Artist")


async def test_metadata_cascade_returns_first_hit() -> None:
    metadata = await MetadataCascade([EmptyProvider(), HitProvider()]).lookup(title="Song")

    assert metadata == TrackMetadata(title="Song", artist="Artist")
