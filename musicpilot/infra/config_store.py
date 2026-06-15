from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4


class ConfigStore:
    def __init__(self, *, runtime_path: Path) -> None:
        self.runtime_path = runtime_path

    def list_downloaders(self) -> list[dict[str, Any]]:
        return self._read_runtime().get("downloaders", [])

    def add_downloader(self, downloader: dict[str, Any]) -> dict[str, Any]:
        payload = self._read_runtime()
        downloaders = payload.setdefault("downloaders", [])
        downloader = {**downloader, "id": uuid4().hex}
        if downloader.get("is_default") or not downloaders:
            for item in downloaders:
                item["is_default"] = False
            downloader["is_default"] = True
        downloaders.append(downloader)
        self._write_runtime(payload)
        return downloader

    def get_downloader(self, downloader_id: str) -> dict[str, Any] | None:
        for downloader in self.list_downloaders():
            if downloader.get("id") == downloader_id:
                return downloader
        return None

    def update_downloader(
        self,
        downloader_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload = self._read_runtime()
        downloaders = payload.setdefault("downloaders", [])
        for index, downloader in enumerate(downloaders):
            if downloader.get("id") == downloader_id:
                if not updates.get("password"):
                    updates.pop("password", None)
                updated = {**downloader, **updates, "id": downloader_id}
                if updated.get("is_default"):
                    for item in downloaders:
                        item["is_default"] = False
                downloaders[index] = updated
                self._write_runtime(payload)
                return updated
        return None

    def default_downloader(self) -> dict[str, Any] | None:
        for downloader in self.list_downloaders():
            if downloader.get("is_default"):
                return downloader
        downloaders = self.list_downloaders()
        return downloaders[0] if downloaders else None

    def list_notifiers(self) -> list[dict[str, Any]]:
        return self._read_runtime().get("notifiers", [])

    def add_notifier(self, notifier: dict[str, Any]) -> dict[str, Any]:
        payload = self._read_runtime()
        notifiers = payload.setdefault("notifiers", [])
        notifier = {**notifier, "id": uuid4().hex}
        notifiers.append(notifier)
        self._write_runtime(payload)
        return notifier

    def get_notifier(self, notifier_id: str) -> dict[str, Any] | None:
        for notifier in self.list_notifiers():
            if notifier.get("id") == notifier_id:
                return notifier
        return None

    def update_notifier(
        self,
        notifier_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload = self._read_runtime()
        notifiers = payload.setdefault("notifiers", [])
        for index, notifier in enumerate(notifiers):
            if notifier.get("id") == notifier_id:
                if not updates.get("bot_token"):
                    updates.pop("bot_token", None)
                updated = {**notifier, **updates, "id": notifier_id}
                notifiers[index] = updated
                self._write_runtime(payload)
                return updated
        return None

    def get_system_settings(self) -> dict[str, Any]:
        payload = self._read_runtime()
        system = payload.setdefault("system", {})
        proxy = system.setdefault("proxy", {})
        return {
            "proxy": {
                "host": str(proxy.get("host", "")),
                "port": int(proxy.get("port") or 0),
                "username": str(proxy.get("username", "")),
                "password": str(proxy.get("password", "")),
            }
        }

    def update_system_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        payload = self._read_runtime()
        system = payload.setdefault("system", {})
        current_proxy = system.setdefault("proxy", {})
        proxy_updates = updates.get("proxy", {})
        if isinstance(proxy_updates, dict):
            if not proxy_updates.get("password"):
                proxy_updates.pop("password", None)
            current_proxy.update(proxy_updates)
            current_proxy.setdefault("host", "")
            current_proxy.setdefault("port", 0)
            current_proxy.setdefault("username", "")
            current_proxy.setdefault("password", "")
        self._write_runtime(payload)
        return self.get_system_settings()

    def _read_runtime(self) -> dict[str, Any]:
        if not self.runtime_path.exists():
            return {"downloaders": [], "notifiers": []}
        payload = json.loads(self.runtime_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"downloaders": [], "notifiers": []}
        payload.setdefault("downloaders", [])
        payload.setdefault("notifiers", [])
        payload.setdefault("system", {"proxy": {}})
        return payload

    def _write_runtime(self, payload: dict[str, Any]) -> None:
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
