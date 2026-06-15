from __future__ import annotations

from typing import Protocol

from musicpilot.core.events import NotifyEvent


class BotAdapter(Protocol):
    @property
    def name(self) -> str: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def send_notification(self, event: NotifyEvent) -> None: ...
