from __future__ import annotations

from typing import Protocol

from musicpilot.core.events import SearchResult


class Indexer(Protocol):
    @property
    def name(self) -> str: ...

    async def search(self, query: str, *, limit: int = 20) -> tuple[SearchResult, ...]: ...
