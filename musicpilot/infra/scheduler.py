from __future__ import annotations

import logging

from musicpilot.infra.db.repositories import SqlAlchemyMediaRepository

logger = logging.getLogger(__name__)


class SubscriptionScheduler:
    def __init__(
        self,
        *,
        repository: SqlAlchemyMediaRepository,
        interval_minutes: int,
        enabled: bool = True,
    ) -> None:
        self.repository = repository
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self._scheduler = None

    def start(self) -> None:
        if not self.enabled:
            return
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self.check_subscriptions,
            "interval",
            minutes=self.interval_minutes,
            id="musicpilot-subscription-check",
            replace_existing=True,
        )
        self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)

    async def check_subscriptions(self) -> None:
        subscriptions = await self.repository.list_subscriptions()
        for subscription in subscriptions:
            if not subscription.enabled:
                continue
            logger.info("Checked subscription %s:%s", subscription.kind, subscription.name)
            await self.repository.mark_subscription_checked(subscription.id)
