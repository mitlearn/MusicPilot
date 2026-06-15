from __future__ import annotations

from musicpilot.core.events import NotifyEvent


class NullBotAdapter:
    @property
    def name(self) -> str:
        return "null"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send_notification(self, event: NotifyEvent) -> None:
        del event
        return None
