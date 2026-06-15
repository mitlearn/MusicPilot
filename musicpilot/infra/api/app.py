from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from secrets import compare_digest
from urllib.parse import quote

import httpx
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from musicpilot.adapters.bots import TelegramBotAdapter, TelegramHttpNotifier
from musicpilot.adapters.downloaders import QBittorrentClient
from musicpilot.adapters.indexers import build_nexusphp_indexers, load_parser_catalog
from musicpilot.adapters.indexers.nexusphp import (
    NexusPHPCrawler,
    NexusPHPParserConfig,
    NexusPHPSiteConfig,
)
from musicpilot.adapters.metadata import MusicBrainzProvider, MutagenTagWriter
from musicpilot.adapters.notifiers import NavidromeNotifier
from musicpilot.core.event_bus import EventBus
from musicpilot.core.events import DownloadCompletedEvent, DownloadEvent, SearchEvent, SearchResult
from musicpilot.core.metadata import MetadataCascade
from musicpilot.core.pipeline import MusicPipeline
from musicpilot.core.processor import MediaProcessor
from musicpilot.infra.api.schemas import (
    DownloaderCreateRequest,
    DownloaderResponse,
    DownloadRequest,
    DownloadResponse,
    DownloadTaskResponse,
    HealthResponse,
    IndexerResponse,
    LogEntryResponse,
    LoginRequest,
    LoginResponse,
    MediaFileResponse,
    NexusPHPParserRequest,
    NotifierCreateRequest,
    NotifierResponse,
    ParserFieldRequest,
    QBittorrentWebhookRequest,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
    SiteCreateRequest,
    SiteResponse,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    SystemSettingsRequest,
    SystemSettingsResponse,
    TestResponse,
)
from musicpilot.infra.auth import issue_session, require_session
from musicpilot.infra.config import Settings
from musicpilot.infra.config_store import ConfigStore
from musicpilot.infra.db import Database, SqlAlchemyMediaRepository
from musicpilot.infra.db.models import IndexerSite
from musicpilot.infra.scheduler import SubscriptionScheduler


class AppState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logs: deque[dict[str, str]] = deque(maxlen=500)
        self.log_handler = AppLogHandler(self.logs)
        self.event_bus = EventBus()
        self.database = Database(settings.database_url)
        self.config_store = ConfigStore(runtime_path=settings.runtime_config)
        self.parser_catalog = load_parser_catalog(settings.indexer_parser_config)
        self.indexers = ()
        self.repository = SqlAlchemyMediaRepository(self.database)
        self.scheduler = SubscriptionScheduler(
            repository=self.repository,
            interval_minutes=settings.subscription_check_interval_minutes,
            enabled=settings.subscriptions_enabled,
        )
        self.downloader = self._build_downloader(settings, self.config_store)
        self.metadata = MetadataCascade(
            [MusicBrainzProvider(user_agent=settings.musicbrainz_user_agent)]
        )
        self.notifiers = self._build_notifiers(settings)
        self.configured_notifiers = self._build_configured_notifiers()
        self.bots = self._build_bots(settings)
        self.notification_sinks = (*self.notifiers, *self.configured_notifiers, *self.bots)
        self.media_processor = MediaProcessor(
            library_root=settings.music_library_path,
            metadata=self.metadata,
            downloader=self.downloader,
            repository=self.repository,
            tag_writer=MutagenTagWriter() if settings.write_audio_tags else None,
        )
        self.pipeline = MusicPipeline(
            event_bus=self.event_bus,
            indexers=self.indexers,
            downloader=self.downloader,
            media_processor=self.media_processor,
            notifiers=self.notification_sinks,
        )

    async def reload_indexers(self) -> None:
        self.reload_parser_catalog()
        sites = [_site_payload(site) for site in await self.repository.list_indexer_sites()]
        self.indexers = build_nexusphp_indexers(sites, self.parser_catalog)
        self.pipeline.indexers = self.indexers

    def reload_parser_catalog(self) -> None:
        self.parser_catalog = load_parser_catalog(self.settings.indexer_parser_config)

    def reload_downloader(self) -> None:
        self.downloader = self._build_downloader(self.settings, self.config_store)
        self.pipeline.downloader = self.downloader
        self.media_processor.downloader = self.downloader

    def reload_notifiers(self) -> None:
        self.configured_notifiers = self._build_configured_notifiers()
        self.notification_sinks = (*self.notifiers, *self.configured_notifiers, *self.bots)
        self.pipeline.notifiers = self.notification_sinks

    @staticmethod
    def _build_downloader(
        settings: Settings,
        config_store: ConfigStore,
    ) -> QBittorrentClient | None:
        configured = config_store.default_downloader()
        if configured is not None:
            return QBittorrentClient(
                str(configured["base_url"]),
                username=str(configured["username"]),
                password=str(configured["password"]),
                download_path=str(configured.get("download_path", "")),
            )
        if not (
            settings.qbittorrent_base_url
            and settings.qbittorrent_username
            and settings.qbittorrent_password
        ):
            return None
        return QBittorrentClient(
            settings.qbittorrent_base_url,
            username=settings.qbittorrent_username,
            password=settings.qbittorrent_password,
            download_path=str(settings.download_staging_path),
        )

    @staticmethod
    def _build_notifiers(settings: Settings) -> tuple[NavidromeNotifier, ...]:
        if not settings.navidrome_base_url:
            return ()
        return (
            NavidromeNotifier(
                settings.navidrome_base_url,
                username=settings.navidrome_username,
                password=settings.navidrome_password,
                token=settings.navidrome_token,
            ),
        )

    def _build_bots(self, settings: Settings) -> tuple[TelegramBotAdapter, ...]:
        if not settings.telegram_bot_token:
            return ()
        chat_ids = tuple(
            int(item.strip())
            for item in settings.telegram_chat_ids.split(",")
            if item.strip()
        )
        return (
            TelegramBotAdapter(
                token=settings.telegram_bot_token,
                event_bus=self.event_bus,
                chat_ids=chat_ids,
            ),
        )

    def _build_configured_notifiers(self) -> tuple[TelegramHttpNotifier, ...]:
        system_settings = self.config_store.get_system_settings()
        notifiers: list[TelegramHttpNotifier] = []
        for item in self.config_store.list_notifiers():
            if item.get("type", "telegram") != "telegram":
                continue
            token = str(item.get("bot_token", "")).strip()
            if not token:
                continue
            chat_ids = tuple(
                int(chat_id.strip())
                for chat_id in str(item.get("chat_ids", "")).split(",")
                if chat_id.strip().isdigit()
            )
            notifiers.append(
                TelegramHttpNotifier(
                    token=token,
                    chat_ids=chat_ids,
                    proxy=_proxy_url(system_settings) if item.get("use_proxy") else None,
                )
            )
        return tuple(notifiers)

    def add_log(self, category: str, message: str, level: str = "INFO") -> None:
        self.logs.appendleft(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": level,
                "message": message,
                "category": category,
            }
        )


class AppLogHandler(logging.Handler):
    def __init__(self, entries: deque[dict[str, str]]) -> None:
        super().__init__(level=logging.INFO)
        self.entries = entries

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            message = str(record.msg)
        self.entries.appendleft(
            {
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "message": message,
                "category": _category_from_logger(record.name),
            }
        )


def create_app() -> FastAPI:
    settings = Settings()
    state = AppState(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.musicpilot = state
        root_logger = logging.getLogger()
        if root_logger.level > logging.INFO:
            root_logger.setLevel(logging.INFO)
        root_logger.addHandler(state.log_handler)
        state.add_log("system", "MusicPilot started")
        await state.database.create_all()
        await state.reload_indexers()
        state.pipeline.start()
        state.scheduler.start()
        for bot in state.bots:
            await bot.start()
        yield
        state.add_log("system", "MusicPilot stopping")
        root_logger.removeHandler(state.log_handler)
        for bot in state.bots:
            await bot.stop()
        state.scheduler.stop()
        await state.pipeline.stop()
        if state.downloader is not None:
            await state.downloader.close()
        for provider in state.metadata.providers:
            close = getattr(provider, "close", None)
            if close is not None:
                await close()
        await state.database.dispose()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        dependencies=[Depends(require_session)],
    )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(app=settings.app_name)

    @app.post("/api/auth/login", response_model=LoginResponse)
    async def login(payload: LoginRequest, response: Response) -> LoginResponse:
        if not (
            compare_digest(payload.username, settings.admin_username)
            and compare_digest(payload.password, settings.admin_password)
        ):
            raise HTTPException(status_code=401, detail="Invalid username or password.")
        issue_session(response, username=payload.username, secret=settings.session_secret)
        return LoginResponse(status="ok", username=payload.username)

    @app.post("/api/search", response_model=SearchResponse)
    async def search(payload: SearchRequest) -> SearchResponse:
        state.add_log("search", f"Search started: {payload.query}")
        results = await state.pipeline.search(SearchEvent(payload.query, limit=payload.limit))
        state.add_log("search", f"Search completed: {payload.query}, {len(results)} result(s)")
        return SearchResponse(
            query=payload.query,
            results=[
                SearchResultResponse(
                    title=result.title,
                    download_url=result.download_url,
                    source=result.source,
                    seeders=result.seeders,
                    leechers=result.leechers,
                    size_bytes=result.size_bytes,
                    details_url=result.details_url,
                    subtitle=result.subtitle,
                    published_at=result.published_at,
                    promotion=result.promotion,
                )
                for result in results
            ],
        )

    @app.get("/api/search/stream")
    async def search_stream(query: str, limit: int = 20) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            if not state.indexers:
                state.add_log(
                    "search",
                    f"Search skipped: no indexer configured for {query}",
                    "WARNING",
                )
                yield _sse("done", {"count": 0})
                return

            state.add_log("search", f"Search started: {query}")
            tasks = [
                asyncio.create_task(_search_indexer(indexer, query, limit))
                for indexer in state.indexers
            ]
            count = 0
            for task in asyncio.as_completed(tasks):
                try:
                    _source, results = await task
                except Exception as exc:  # noqa: BLE001
                    state.add_log("search", f"Indexer failed: {exc}", "ERROR")
                    yield _sse("error", {"source": "unknown", "message": str(exc)})
                    continue
                for result in results:
                    count += 1
                    yield _sse(
                        "result",
                        {
                            "title": result.title,
                            "download_url": result.download_url,
                            "source": result.source,
                            "seeders": result.seeders,
                            "leechers": result.leechers,
                            "size_bytes": result.size_bytes,
                            "details_url": result.details_url,
                            "subtitle": result.subtitle,
                            "published_at": result.published_at,
                            "promotion": result.promotion,
                        },
                    )
            state.add_log("search", f"Search completed: {query}, {count} result(s)")
            yield _sse("done", {"count": count})

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/api/downloads", response_model=DownloadResponse, status_code=202)
    async def add_download(payload: DownloadRequest) -> DownloadResponse:
        if state.downloader is None:
            state.reload_downloader()
        if state.downloader is None:
            state.add_log(
                "download",
                f"Download rejected: no downloader for {payload.title}",
                "ERROR",
            )
            raise HTTPException(status_code=503, detail="No downloader is configured.")
        result = SearchResult(
            title=payload.title,
            download_url=payload.download_url,
            source=payload.source,
            seeders=payload.seeders,
            leechers=payload.leechers,
            size_bytes=payload.size_bytes,
            details_url=payload.details_url,
            subtitle=payload.subtitle,
            published_at=payload.published_at,
            promotion=payload.promotion,
        )
        await state.event_bus.publish(DownloadEvent(result, category=payload.category))
        state.add_log("download", f"Download queued: {payload.title}")
        return DownloadResponse(status="queued")

    @app.get("/api/downloads", response_model=list[DownloadTaskResponse])
    async def downloads() -> list[DownloadTaskResponse]:
        if state.downloader is None:
            state.reload_downloader()
        if state.downloader is None:
            return []
        statuses = await state.downloader.list_statuses()
        return [
            DownloadTaskResponse(
                torrent_hash=item.torrent_hash,
                name=item.name,
                state=item.state.value,
                progress=item.progress,
                save_path=str(item.save_path) if item.save_path is not None else None,
            )
            for item in statuses
        ]

    @app.get("/api/indexers", response_model=list[IndexerResponse])
    async def indexers() -> list[IndexerResponse]:
        return [IndexerResponse(name=indexer.name) for indexer in state.indexers]

    @app.get("/api/sites", response_model=list[SiteResponse])
    async def sites() -> list[SiteResponse]:
        return [
            _site_response(site, _supported_parser_or_422(state, site.base_url))
            for site in await state.repository.list_indexer_sites()
        ]

    @app.post("/api/sites/test", response_model=TestResponse)
    async def test_site(payload: SiteCreateRequest) -> TestResponse:
        parser = _supported_parser_or_422(state, payload.base_url)
        crawler = NexusPHPCrawler(
            NexusPHPSiteConfig(
                name=payload.name,
                base_url=payload.base_url,
                cookie=payload.cookie,
                user_agent=payload.user_agent,
                parser=parser,
                max_concurrency=payload.max_concurrency,
            )
        )
        result = await crawler.test_auth()
        return TestResponse(ok=result.ok, message=result.message)

    @app.post("/api/sites", response_model=SiteResponse, status_code=201)
    async def create_site(payload: SiteCreateRequest) -> SiteResponse:
        parser = _supported_parser_or_422(state, payload.base_url)
        try:
            site = await state.repository.create_indexer_site(**payload.model_dump())
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Site already exists.") from exc
        await state.reload_indexers()
        return _site_response(site, parser)

    @app.put("/api/sites/{site_id}", response_model=SiteResponse)
    async def update_site(site_id: str, payload: SiteCreateRequest) -> SiteResponse:
        parser = _supported_parser_or_422(state, payload.base_url)
        try:
            site = await state.repository.update_indexer_site(site_id, **payload.model_dump())
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Site already exists.") from exc
        if site is None:
            raise HTTPException(status_code=404, detail="Site not found.")
        await state.reload_indexers()
        return _site_response(site, parser)

    @app.get("/api/settings/downloaders", response_model=list[DownloaderResponse])
    async def downloaders() -> list[DownloaderResponse]:
        return [
            _downloader_response(item)
            for item in state.config_store.list_downloaders()
        ]

    @app.post("/api/settings/downloaders", response_model=DownloaderResponse, status_code=201)
    async def create_downloader(payload: DownloaderCreateRequest) -> DownloaderResponse:
        if not payload.password:
            raise HTTPException(status_code=422, detail="Password is required.")
        downloader = state.config_store.add_downloader(payload.model_dump())
        state.reload_downloader()
        return _downloader_response(downloader)

    @app.put("/api/settings/downloaders/{downloader_id}", response_model=DownloaderResponse)
    async def update_downloader(
        downloader_id: str,
        payload: DownloaderCreateRequest,
    ) -> DownloaderResponse:
        downloader = state.config_store.update_downloader(downloader_id, payload.model_dump())
        if downloader is None:
            raise HTTPException(status_code=404, detail="Downloader not found.")
        state.reload_downloader()
        return _downloader_response(downloader)

    @app.post("/api/settings/downloaders/test", response_model=TestResponse)
    async def test_downloader(payload: DownloaderCreateRequest) -> TestResponse:
        password = payload.password
        if not password and payload.id:
            existing = state.config_store.get_downloader(payload.id)
            password = str(existing.get("password", "")) if existing else ""
        if not password:
            return TestResponse(ok=False, message="下载器密码不能为空。")
        client = QBittorrentClient(
            payload.base_url,
            username=payload.username,
            password=password,
            download_path=payload.download_path,
        )
        try:
            await client.test_connection()
        except Exception as exc:  # noqa: BLE001
            return TestResponse(ok=False, message=f"下载器连接失败：{exc}")
        finally:
            await client.close()
        return TestResponse(ok=True, message="qBittorrent 登录成功")

    @app.get("/api/settings/system", response_model=SystemSettingsResponse)
    async def system_settings() -> SystemSettingsResponse:
        return SystemSettingsResponse(**state.config_store.get_system_settings())

    @app.put("/api/settings/system", response_model=SystemSettingsResponse)
    async def update_system_settings(
        payload: SystemSettingsRequest,
    ) -> SystemSettingsResponse:
        settings_payload = state.config_store.update_system_settings(payload.model_dump())
        state.reload_notifiers()
        state.add_log("settings", "System settings saved")
        return SystemSettingsResponse(**settings_payload)

    @app.get("/api/settings/notifiers", response_model=list[NotifierResponse])
    async def notifiers() -> list[NotifierResponse]:
        return [_notifier_response(item) for item in state.config_store.list_notifiers()]

    @app.post("/api/settings/notifiers", response_model=NotifierResponse, status_code=201)
    async def create_notifier(payload: NotifierCreateRequest) -> NotifierResponse:
        if not payload.bot_token:
            raise HTTPException(status_code=422, detail="Bot token is required.")
        notifier = state.config_store.add_notifier(payload.model_dump())
        state.reload_notifiers()
        return _notifier_response(notifier)

    @app.put("/api/settings/notifiers/{notifier_id}", response_model=NotifierResponse)
    async def update_notifier(
        notifier_id: str,
        payload: NotifierCreateRequest,
    ) -> NotifierResponse:
        notifier = state.config_store.update_notifier(notifier_id, payload.model_dump())
        if notifier is None:
            raise HTTPException(status_code=404, detail="Notifier not found.")
        state.reload_notifiers()
        return _notifier_response(notifier)

    @app.post("/api/settings/notifiers/test", response_model=TestResponse)
    async def test_notifier(payload: NotifierCreateRequest) -> TestResponse:
        bot_token = payload.bot_token
        if not bot_token and payload.id:
            existing = state.config_store.get_notifier(payload.id)
            bot_token = str(existing.get("bot_token", "")) if existing else ""
        if not bot_token:
            return TestResponse(ok=False, message="Telegram Bot Token 不能为空。")
        proxy = _proxy_url(state.config_store.get_system_settings()) if payload.use_proxy else None
        if payload.use_proxy and proxy is None:
            return TestResponse(ok=False, message="已开启代理，但系统代理地址未配置。")
        state.add_log(
            "notify",
            f"Telegram notifier test started: {payload.name}, proxy={'on' if proxy else 'off'}",
        )
        try:
            async with httpx.AsyncClient(timeout=20, proxy=proxy) as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{bot_token}/getMe"
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            message = f"Telegram Bot 测试超时：{exc or '请求超过 20 秒未返回'}"
            state.add_log("notify", message, "ERROR")
            return TestResponse(ok=False, message=message)
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            message = f"Telegram Bot 测试失败：HTTP {exc.response.status_code} {body}"
            state.add_log("notify", message, "ERROR")
            return TestResponse(ok=False, message=message)
        except httpx.RequestError as exc:
            message = f"Telegram Bot 连接失败：{exc.__class__.__name__}: {exc}"
            state.add_log("notify", message, "ERROR")
            return TestResponse(ok=False, message=message)
        except Exception as exc:  # noqa: BLE001
            message = f"Telegram Bot 测试失败：{exc.__class__.__name__}: {exc}"
            state.add_log("notify", message, "ERROR")
            return TestResponse(ok=False, message=message)

        if not data.get("ok"):
            message = str(data.get("description", "Bot 不可用"))
            state.add_log("notify", f"Telegram notifier test failed: {message}", "ERROR")
            return TestResponse(ok=False, message=message)
        username = data.get("result", {}).get("username", "")
        state.add_log("notify", f"Telegram notifier test succeeded: {username}")
        return TestResponse(ok=True, message=f"Telegram Bot 可用：{username}")

    @app.get("/api/logs", response_model=list[LogEntryResponse])
    async def logs(limit: int = 200) -> list[LogEntryResponse]:
        limited = max(1, min(limit, 500))
        return [LogEntryResponse(**entry) for entry in list(state.logs)[:limited]]

    @app.get("/api/media", response_model=list[MediaFileResponse])
    async def media_files() -> list[MediaFileResponse]:
        rows = await state.repository.list_media_files()
        return [
            MediaFileResponse(
                id=row.id,
                torrent_hash=row.torrent_hash,
                source_path=row.source_path,
                library_path=row.library_path,
                title=row.title,
                artist=row.artist,
                album=row.album,
                year=row.year,
                track_number=row.track_number,
            )
            for row in rows
        ]

    @app.get("/api/subscriptions", response_model=list[SubscriptionResponse])
    async def subscriptions() -> list[SubscriptionResponse]:
        rows = await state.repository.list_subscriptions()
        return [
            SubscriptionResponse(
                id=row.id,
                kind=row.kind,
                name=row.name,
                external_id=row.external_id,
                enabled=row.enabled,
                last_checked_at=row.last_checked_at,
            )
            for row in rows
        ]

    @app.post("/api/subscriptions", response_model=SubscriptionResponse, status_code=201)
    async def create_subscription(payload: SubscriptionCreateRequest) -> SubscriptionResponse:
        row = await state.repository.create_subscription(
            kind=payload.kind,
            name=payload.name,
            external_id=payload.external_id,
            enabled=payload.enabled,
        )
        return SubscriptionResponse(
            id=row.id,
            kind=row.kind,
            name=row.name,
            external_id=row.external_id,
            enabled=row.enabled,
            last_checked_at=row.last_checked_at,
        )

    @app.post("/api/webhooks/qbittorrent/{torrent_hash}", status_code=202)
    async def qbittorrent_webhook(
        torrent_hash: str,
        payload: QBittorrentWebhookRequest | None = None,
    ) -> dict[str, str]:
        download_path = (
            None
            if payload is None or payload.download_path is None
            else Path(payload.download_path)
        )
        await state.event_bus.publish(DownloadCompletedEvent(torrent_hash, download_path))
        state.add_log("transfer", f"Download completed webhook accepted: {torrent_hash}")
        return {"status": "accepted", "torrent_hash": torrent_hash}

    if settings.static_dir.exists():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")

    return app


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _search_indexer(
    indexer: object,
    query: str,
    limit: int,
) -> tuple[str, tuple[SearchResult, ...]]:
    results = await indexer.search(query, limit=limit)
    return indexer.name, results


def _downloader_response(item: dict[str, object]) -> DownloaderResponse:
    return DownloaderResponse(
        id=str(item.get("id")) if item.get("id") else None,
        name=str(item.get("name", "qBittorrent")),
        type=str(item.get("type", "qbittorrent")),
        base_url=str(item.get("base_url", "")),
        username=str(item.get("username", "")),
        download_path=str(item.get("download_path", "")),
        is_default=bool(item.get("is_default", False)),
    )


def _notifier_response(item: dict[str, object]) -> NotifierResponse:
    return NotifierResponse(
        id=str(item.get("id")) if item.get("id") else None,
        name=str(item.get("name", "Telegram Bot")),
        type=str(item.get("type", "telegram")),
        chat_ids=str(item.get("chat_ids", "")),
        use_proxy=bool(item.get("use_proxy", False)),
    )


def _site_payload(site: IndexerSite) -> dict[str, object]:
    return {
        "id": site.id,
        "name": site.name,
        "base_url": site.base_url,
        "cookie": site.cookie,
        "user_agent": site.user_agent,
        "max_concurrency": site.max_concurrency,
    }


def _site_response(site: IndexerSite, parser: NexusPHPParserConfig) -> SiteResponse:
    return SiteResponse(**_site_payload(site), parser=_parser_response(parser))


def _parser_response(parser: NexusPHPParserConfig) -> NexusPHPParserRequest:
    return NexusPHPParserRequest(
        list_selector=parser.list_selector,
        fields={
            name: ParserFieldRequest(
                selector=field.selector,
                attribute=field.attribute,
                regex=field.regex,
                index=field.index,
                remove=list(field.remove),
                filters=list(field.filters),
            )
            for name, field in parser.fields.items()
        },
    )


def _supported_parser_or_422(state: AppState, base_url: str) -> NexusPHPParserConfig:
    state.reload_parser_catalog()
    entry = state.parser_catalog.match(base_url)
    if entry is None:
        raise HTTPException(
            status_code=422,
            detail="当前站点暂不支持，请先在 sites.parser.yaml 中配置解析器。",
        )
    return entry.parser


def _proxy_url(settings_payload: dict[str, object]) -> str | None:
    proxy = settings_payload.get("proxy", {})
    if not isinstance(proxy, dict):
        return None
    host = str(proxy.get("host", "")).strip()
    if not host:
        return None
    port = int(proxy.get("port") or 0)
    username = str(proxy.get("username", "")).strip()
    password = str(proxy.get("password", "")).strip()
    auth = ""
    if username:
        auth = quote(username)
        if password:
            auth = f"{auth}:{quote(password)}"
        auth = f"{auth}@"
    if host.startswith(("http://", "https://", "socks5://", "socks4://")):
        scheme, rest = host.split("://", 1)
        return f"{scheme}://{auth}{rest}"
    if port:
        return f"http://{auth}{host}:{port}"
    return f"http://{auth}{host}"


def _category_from_logger(name: str) -> str:
    if "indexer" in name:
        return "search"
    if "download" in name:
        return "download"
    if "processor" in name or "library" in name or "metadata" in name:
        return "transfer"
    if "notifier" in name or "bot" in name:
        return "notify"
    return "system"
