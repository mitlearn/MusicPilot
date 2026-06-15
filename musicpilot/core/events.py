from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class EventType(StrEnum):
    SEARCH_REQUESTED = "search.requested"
    SEARCH_COMPLETED = "search.completed"
    DOWNLOAD_REQUESTED = "download.requested"
    DOWNLOAD_COMPLETED = "download.completed"
    MEDIA_PROCESSED = "media.processed"
    NOTIFY_REQUESTED = "notify.requested"


@dataclass(frozen=True, slots=True)
class Event:
    event_type: EventType
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class SearchResult:
    title: str
    download_url: str
    source: str
    seeders: int = 0
    leechers: int = 0
    size_bytes: int | None = None
    details_url: str | None = None
    subtitle: str | None = None
    published_at: str | None = None
    promotion: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def identity_key(self) -> tuple[str, str]:
        return (self.source.lower(), self.download_url)


@dataclass(frozen=True, slots=True)
class ProcessedMedia:
    source_path: Path
    library_path: Path
    title: str
    artist: str | None = None
    album: str | None = None
    year: int | None = None
    track_number: int | None = None


@dataclass(frozen=True, slots=True)
class SearchEvent(Event):
    query: str = ""
    interactive: bool = True
    limit: int = 20

    def __init__(self, query: str, interactive: bool = True, limit: int = 20) -> None:
        object.__setattr__(self, "event_type", EventType.SEARCH_REQUESTED)
        object.__setattr__(self, "correlation_id", str(uuid4()))
        object.__setattr__(self, "created_at", datetime.now(UTC))
        object.__setattr__(self, "query", query)
        object.__setattr__(self, "interactive", interactive)
        object.__setattr__(self, "limit", limit)


@dataclass(frozen=True, slots=True)
class SearchCompletedEvent(Event):
    query: str = ""
    results: tuple[SearchResult, ...] = ()

    def __init__(self, query: str, results: tuple[SearchResult, ...], correlation_id: str) -> None:
        object.__setattr__(self, "event_type", EventType.SEARCH_COMPLETED)
        object.__setattr__(self, "correlation_id", correlation_id)
        object.__setattr__(self, "created_at", datetime.now(UTC))
        object.__setattr__(self, "query", query)
        object.__setattr__(self, "results", results)


@dataclass(frozen=True, slots=True)
class DownloadEvent(Event):
    result: SearchResult | None = None
    category: str = "MusicPilot"

    def __init__(self, result: SearchResult, category: str = "MusicPilot") -> None:
        object.__setattr__(self, "event_type", EventType.DOWNLOAD_REQUESTED)
        object.__setattr__(self, "correlation_id", str(uuid4()))
        object.__setattr__(self, "created_at", datetime.now(UTC))
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "category", category)


@dataclass(frozen=True, slots=True)
class DownloadCompletedEvent(Event):
    torrent_hash: str = ""
    download_path: Path | None = None

    def __init__(self, torrent_hash: str, download_path: Path | None = None) -> None:
        object.__setattr__(self, "event_type", EventType.DOWNLOAD_COMPLETED)
        object.__setattr__(self, "correlation_id", str(uuid4()))
        object.__setattr__(self, "created_at", datetime.now(UTC))
        object.__setattr__(self, "torrent_hash", torrent_hash)
        object.__setattr__(self, "download_path", download_path)


@dataclass(frozen=True, slots=True)
class MediaProcessedEvent(Event):
    torrent_hash: str = ""
    items: tuple[ProcessedMedia, ...] = ()

    def __init__(self, torrent_hash: str, items: tuple[ProcessedMedia, ...]) -> None:
        object.__setattr__(self, "event_type", EventType.MEDIA_PROCESSED)
        object.__setattr__(self, "correlation_id", str(uuid4()))
        object.__setattr__(self, "created_at", datetime.now(UTC))
        object.__setattr__(self, "torrent_hash", torrent_hash)
        object.__setattr__(self, "items", items)


@dataclass(frozen=True, slots=True)
class NotifyEvent(Event):
    title: str = ""
    text: str = ""
    cover_url: str | None = None

    def __init__(self, title: str, text: str, cover_url: str | None = None) -> None:
        object.__setattr__(self, "event_type", EventType.NOTIFY_REQUESTED)
        object.__setattr__(self, "correlation_id", str(uuid4()))
        object.__setattr__(self, "created_at", datetime.now(UTC))
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "cover_url", cover_url)
