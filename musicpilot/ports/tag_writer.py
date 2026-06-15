from __future__ import annotations

from pathlib import Path
from typing import Protocol

from musicpilot.ports.metadata import TrackMetadata


class TagWriter(Protocol):
    async def write(self, path: Path, metadata: TrackMetadata) -> None: ...
