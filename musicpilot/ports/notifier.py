from __future__ import annotations

from typing import Protocol

from musicpilot.core.events import NotifyEvent


class Notifier(Protocol):
    @property
    def name(self) -> str: ...

    async def notify(self, event: NotifyEvent) -> None: ...
