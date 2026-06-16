from __future__ import annotations

import logging
from collections.abc import Iterable

from musicpilot.ports.metadata import MetadataProvider, TrackMetadata

logger = logging.getLogger(__name__)


class MetadataCascade:
    def __init__(self, providers: Iterable[MetadataProvider]) -> None:
        self.providers = tuple(providers)

    async def lookup(self, *, title: str, artist: str | None = None) -> TrackMetadata | None:
        candidates = await self.search_metadata(title=title, artist=artist, limit=1)
        return candidates[0] if candidates else None

    async def search_metadata(
        self,
        *,
        title: str,
        artist: str | None = None,
        limit: int = 5,
    ) -> tuple[TrackMetadata, ...]:
        candidates: list[TrackMetadata] = []
        for provider in self.providers:
            try:
                search = getattr(provider, "search_metadata", None)
                if search is None:
                    metadata = await provider.lookup(title=title, artist=artist)
                    provider_candidates = (metadata,) if metadata is not None else ()
                else:
                    provider_candidates = await search(title=title, artist=artist, limit=limit)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Metadata provider %s failed: %s", provider.name, exc)
                continue
            candidates.extend(item for item in provider_candidates if item is not None)
            if len(candidates) >= limit:
                return tuple(candidates[:limit])
        return tuple(candidates)
