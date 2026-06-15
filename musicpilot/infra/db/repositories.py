from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from musicpilot.infra.db.models import IndexerSite, MediaFile, Subscription, TorrentRecord
from musicpilot.infra.db.session import Database
from musicpilot.ports.metadata import TrackMetadata


class SqlAlchemyMediaRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def record_processed_media(
        self,
        *,
        torrent_hash: str,
        source_path: Path,
        library_path: Path,
        metadata: TrackMetadata,
    ) -> None:
        async with self.database.session() as session:
            result = await session.execute(
                select(MediaFile).where(MediaFile.library_path == str(library_path))
            )
            media_file = result.scalar_one_or_none()
            if media_file is None:
                media_file = MediaFile(
                    torrent_hash=torrent_hash,
                    source_path=str(source_path),
                    library_path=str(library_path),
                )
                session.add(media_file)

            media_file.torrent_hash = torrent_hash
            media_file.source_path = str(source_path)
            media_file.title = metadata.title
            media_file.artist = metadata.artist
            media_file.album = metadata.album
            media_file.year = metadata.year
            media_file.track_number = metadata.track_number
            media_file.metadata_payload = asdict(metadata)
            await session.commit()

    async def mark_torrent_completed(
        self,
        *,
        torrent_hash: str,
        save_path: Path | None,
    ) -> None:
        async with self.database.session() as session:
            result = await session.execute(
                select(TorrentRecord).where(TorrentRecord.torrent_hash == torrent_hash)
            )
            record = result.scalar_one_or_none()
            if record is None:
                record = TorrentRecord(
                    torrent_hash=torrent_hash,
                    name=torrent_hash,
                    download_url="",
                )
                session.add(record)
            record.status = "completed"
            record.progress = 1.0
            record.save_path = str(save_path) if save_path is not None else None
            await session.commit()

    async def list_subscriptions(self) -> list[Subscription]:
        async with self.database.session() as session:
            result = await session.execute(select(Subscription).order_by(Subscription.id))
            return list(result.scalars().all())

    async def list_media_files(self) -> list[MediaFile]:
        async with self.database.session() as session:
            result = await session.execute(select(MediaFile).order_by(MediaFile.id.desc()))
            return list(result.scalars().all())

    async def create_subscription(
        self,
        *,
        kind: str,
        name: str,
        external_id: str | None = None,
        enabled: bool = True,
    ) -> Subscription:
        async with self.database.session() as session:
            subscription = Subscription(
                kind=kind,
                name=name,
                external_id=external_id,
                enabled=enabled,
                payload={},
            )
            session.add(subscription)
            await session.commit()
            await session.refresh(subscription)
            return subscription

    async def mark_subscription_checked(self, subscription_id: int) -> None:
        async with self.database.session() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            subscription = result.scalar_one_or_none()
            if subscription is None:
                return
            subscription.last_checked_at = datetime.now(UTC)
            await session.commit()

    async def list_indexer_sites(self) -> list[IndexerSite]:
        async with self.database.session() as session:
            result = await session.execute(select(IndexerSite).order_by(IndexerSite.name))
            return list(result.scalars().all())

    async def create_indexer_site(
        self,
        *,
        name: str,
        base_url: str,
        cookie: str | None = None,
        user_agent: str | None = None,
        max_concurrency: int = 2,
    ) -> IndexerSite:
        async with self.database.session() as session:
            site = IndexerSite(
                name=name,
                base_url=base_url,
                cookie=cookie,
                user_agent=user_agent,
                max_concurrency=max_concurrency,
            )
            session.add(site)
            await session.commit()
            await session.refresh(site)
            return site

    async def update_indexer_site(
        self,
        site_id: str,
        *,
        name: str,
        base_url: str,
        cookie: str | None = None,
        user_agent: str | None = None,
        max_concurrency: int = 2,
    ) -> IndexerSite | None:
        async with self.database.session() as session:
            result = await session.execute(select(IndexerSite).where(IndexerSite.id == site_id))
            site = result.scalar_one_or_none()
            if site is None:
                return None
            site.name = name
            site.base_url = base_url
            site.cookie = cookie
            site.user_agent = user_agent
            site.max_concurrency = max_concurrency
            await session.commit()
            await session.refresh(site)
            return site
