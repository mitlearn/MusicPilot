from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    status: str
    username: str


class TestResponse(BaseModel):
    ok: bool
    message: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)


class SearchResultResponse(BaseModel):
    title: str
    download_url: str
    source: str
    seeders: int
    leechers: int = 0
    size_bytes: int | None = None
    details_url: str | None = None
    subtitle: str | None = None
    published_at: str | None = None
    promotion: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultResponse]


class DownloadRequest(BaseModel):
    title: str = Field(min_length=1)
    download_url: str = Field(min_length=1)
    source: str = Field(min_length=1)
    seeders: int = 0
    leechers: int = 0
    size_bytes: int | None = None
    details_url: str | None = None
    subtitle: str | None = None
    published_at: str | None = None
    promotion: str | None = None
    category: str = "MusicPilot"


class DownloadResponse(BaseModel):
    status: str
    torrent_hash: str | None = None


class DownloadTaskResponse(BaseModel):
    torrent_hash: str
    name: str
    state: str
    progress: float
    save_path: str | None = None


class IndexerResponse(BaseModel):
    name: str


class ParserFieldRequest(BaseModel):
    selector: str = Field(min_length=1)
    attribute: str = "text"
    regex: str | None = None
    index: int | None = None
    remove: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)


class NexusPHPParserRequest(BaseModel):
    list_selector: str = Field(
        default="table.torrents tr:has(a[href*='details.php']):has(a[href*='download.php'])",
        min_length=1,
    )
    fields: dict[str, ParserFieldRequest] = Field(default_factory=dict)


class SiteCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=1)
    cookie: str | None = None
    user_agent: str | None = None
    max_concurrency: int = Field(default=2, ge=1, le=10)


class SiteResponse(SiteCreateRequest):
    id: str | None = None
    parser: NexusPHPParserRequest


class DownloaderCreateRequest(BaseModel):
    id: str | None = None
    name: str = Field(default="qBittorrent", min_length=1, max_length=128)
    type: str = Field(default="qbittorrent", pattern="^qbittorrent$")
    base_url: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: str = ""
    download_path: str = ""
    is_default: bool = True


class DownloaderResponse(BaseModel):
    id: str | None = None
    name: str
    type: str
    base_url: str
    username: str
    download_path: str = ""
    is_default: bool


class NotifierCreateRequest(BaseModel):
    id: str | None = None
    name: str = Field(default="Telegram Bot", min_length=1, max_length=128)
    type: str = Field(default="telegram", pattern="^telegram$")
    bot_token: str = ""
    chat_ids: str = ""
    use_proxy: bool = False


class NotifierResponse(BaseModel):
    id: str | None = None
    name: str
    type: str
    chat_ids: str = ""
    use_proxy: bool = False


class ProxySettings(BaseModel):
    host: str = ""
    port: int = Field(default=0, ge=0, le=65535)
    username: str = ""
    password: str = ""


class SystemSettingsRequest(BaseModel):
    proxy: ProxySettings = Field(default_factory=ProxySettings)


class SystemSettingsResponse(BaseModel):
    proxy: ProxySettings


class LogEntryResponse(BaseModel):
    timestamp: str
    level: str
    message: str
    category: str = "system"


class QBittorrentWebhookRequest(BaseModel):
    download_path: str | None = None


class SubscriptionCreateRequest(BaseModel):
    kind: str = Field(pattern="^(artist|album|playlist)$")
    name: str = Field(min_length=1, max_length=512)
    external_id: str | None = None
    enabled: bool = True


class SubscriptionResponse(BaseModel):
    id: int
    kind: str
    name: str
    external_id: str | None
    enabled: bool
    last_checked_at: datetime | None = None


class MediaFileResponse(BaseModel):
    id: int
    torrent_hash: str | None
    source_path: str
    library_path: str
    title: str | None
    artist: str | None
    album: str | None
    year: int | None
    track_number: int | None
