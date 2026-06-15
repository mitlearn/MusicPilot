from __future__ import annotations

import hashlib
from uuid import uuid4

import httpx

from musicpilot.core.events import NotifyEvent


class NavidromeNotifier:
    def __init__(
        self,
        base_url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = token

    @property
    def name(self) -> str:
        return "navidrome"

    async def notify(self, event: NotifyEvent) -> None:
        del event
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20, headers=headers) as client:
            response = await client.get("/rest/startScan.view", params=self._params())
            response.raise_for_status()

    def _params(self) -> dict[str, str]:
        params = {"v": "1.16.1", "c": "MusicPilot", "f": "json"}
        if self.username and self.password:
            salt = uuid4().hex
            token = hashlib.md5(f"{self.password}{salt}".encode()).hexdigest()
            params.update({"u": self.username, "t": token, "s": salt})
        return params
