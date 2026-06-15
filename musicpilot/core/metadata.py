from __future__ import annotations

import logging
from collections.abc import Iterable

from musicpilot.ports.metadata import MetadataProvider, TrackMetadata

logger = logging.getLogger(__name__)


class MetadataCascade:
    def __init__(self, providers: Iterable[MetadataProvider]) -> None:
        self.providers = tuple(providers)

    async def lookup(self, *, title: str, artist: str | None = None) -> TrackMetadata | None:
        for provider in self.providers:
            try:
                metadata = await provider.lookup(title=title, artist=artist)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Metadata provider %s failed: %s", provider.name, exc)
                continue
            if metadata is not None:
                return metadata
        return None
