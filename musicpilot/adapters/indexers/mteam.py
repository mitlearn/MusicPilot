from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx

from musicpilot.adapters.indexers.nexusphp import SiteAuthCheck
from musicpilot.core.events import SearchResult


@dataclass(frozen=True, slots=True)
class MTeamSiteConfig:
    name: str
    base_url: str
    api_key: str | None = None
    site_id: str | None = None
    max_concurrency: int = 2
    user_agent: str | None = None


class MTeamCrawler:
    def __init__(
        self,
        config: MTeamSiteConfig,
        client: httpx.AsyncClient | None = None,
        proxy_url: str | None = None,
    ) -> None:
        self.config = config
        self._client = client
        self._proxy_url = proxy_url
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._request_lock = asyncio.Lock()
        self._last_request_at = 0.0

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def api_base_url(self) -> str:
        hostname = urlparse(self.config.base_url).hostname or ""
        if hostname == "m-team.cc" or hostname.endswith(".m-team.cc"):
            return "https://api.m-team.cc/"
        raise RuntimeError("M-Team 站点地址无效。")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search(self, query: str, *, limit: int = 20) -> tuple[SearchResult, ...]:
        payload = await self._post_json(
            urljoin(self.api_base_url, "api/torrent/search"),
            json={
                "mode": "normal",
                "categories": ["434"],
                "keyword": query,
                "pageNumber": 1,
                "pageSize": min(max(limit, 1), 100),
            },
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            return ()
        items = data.get("data")
        if items is None:
            return ()
        if not isinstance(items, list):
            raise RuntimeError("M-Team 搜索响应格式无效。")

        results: list[SearchResult] = []
        for item in items:
            result = self._search_result(item)
            if result is not None:
                results.append(result)
            if len(results) >= limit:
                break
        return tuple(results)

    async def test_auth(self) -> SiteAuthCheck:
        if not self.config.api_key or not self.config.api_key.strip():
            return SiteAuthCheck(False, "API Key 不能为空，无法验证 M-Team 连接。")
        try:
            await self.search("", limit=1)
        except Exception as exc:  # noqa: BLE001
            return SiteAuthCheck(False, f"M-Team 连接测试失败：{exc}")
        return SiteAuthCheck(True, "M-Team API Key 有效，连接成功。")

    async def download_torrent(self, token_url: str) -> bytes:
        self._validate_token_url(token_url)
        payload = await self._post_json(token_url)
        signed_url = payload.get("data")
        if not isinstance(signed_url, str) or not signed_url.strip():
            raise RuntimeError("M-Team 下载令牌响应未返回临时下载地址。")

        try:
            response = await self._get(signed_url, include_api_key=False)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"M-Team 种子文件下载失败，HTTP {exc.response.status_code}。"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError("M-Team 种子文件下载连接失败。") from exc
        return response.content

    async def _post_json(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.config.api_key or not self.config.api_key.strip():
            raise RuntimeError("M-Team API Key 未配置。")

        try:
            response = await self._post(url, json=json)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 429:
                message = "M-Team 请求过于频繁，请稍后重试。"
            elif status_code in {401, 403}:
                message = "M-Team API Key 无效、请求受限或当前网络需要代理。"
            else:
                message = f"M-Team API 请求失败，HTTP {status_code}。"
            raise RuntimeError(message) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("M-Team API 连接超时。") from exc
        except httpx.ProxyError as exc:
            raise RuntimeError("M-Team API 代理连接失败。") from exc
        except httpx.RequestError as exc:
            raise RuntimeError("M-Team API 网络连接失败。") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("M-Team API 返回的不是有效 JSON。") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("M-Team API 响应格式无效。")
        _validate_api_payload(payload)
        return payload

    async def _post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        async with self._semaphore:
            await self._wait_for_request_slot()
            headers = self._headers(include_api_key=True)
            if self._client is not None:
                if json is None:
                    return await self._client.post(url, headers=headers)
                return await self._client.post(url, headers=headers, json=json)
            async with self._new_client() as client:
                if json is None:
                    return await client.post(url, headers=headers)
                return await client.post(url, headers=headers, json=json)

    async def _get(self, url: str, *, include_api_key: bool) -> httpx.Response:
        headers = self._headers(include_api_key=include_api_key)
        headers["Accept"] = "application/x-bittorrent"
        if self._client is not None:
            return await self._client.get(url, headers=headers)
        async with self._new_client() as client:
            return await client.get(url, headers=headers)

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            http2=True,
            timeout=30,
            follow_redirects=True,
            proxy=self._proxy_url,
        )

    def _headers(self, *, include_api_key: bool) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if include_api_key and self.config.api_key:
            headers["x-api-key"] = self.config.api_key
        if self.config.user_agent:
            headers["User-Agent"] = self.config.user_agent
        return headers

    async def _wait_for_request_slot(self) -> None:
        async with self._request_lock:
            loop = asyncio.get_running_loop()
            wait_seconds = 2.5 - (loop.time() - self._last_request_at)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._last_request_at = loop.time()

    def _validate_token_url(self, token_url: str) -> None:
        parsed = urlparse(token_url)
        api_host = urlparse(self.api_base_url).hostname
        torrent_ids = parse_qs(parsed.query).get("id", [])
        if (
            parsed.scheme != "https"
            or parsed.hostname != api_host
            or parsed.path != "/api/torrent/genDlToken"
            or len(torrent_ids) != 1
            or not torrent_ids[0].isdigit()
        ):
            raise RuntimeError("M-Team 下载令牌地址无效。")

    def _search_result(self, raw: object) -> SearchResult | None:
        if not isinstance(raw, dict):
            return None
        torrent_id = str(raw.get("id") or "").strip()
        title = str(raw.get("name") or "").strip()
        if not torrent_id or not title:
            return None
        status = raw.get("status")
        status_payload = status if isinstance(status, dict) else {}
        created_date = raw.get("createdDate") or status_payload.get("createdDate")
        download_query = urlencode({"id": torrent_id})
        return SearchResult(
            title=" ".join(title.split()),
            download_url=urljoin(
                self.api_base_url,
                f"api/torrent/genDlToken?{download_query}",
            ),
            details_url=urljoin(self.config.base_url.rstrip("/") + "/", f"detail/{torrent_id}"),
            source=self.config.name,
            seeders=_to_int(status_payload.get("seeders")),
            leechers=_to_int(status_payload.get("leechers")),
            size_bytes=_to_int(raw.get("size")) or None,
            subtitle=_optional_text(raw.get("smallDescr")),
            published_at=_optional_text(created_date),
            promotion=_promotion_text(status_payload.get("discount")),
            metadata={
                "type": "music",
                "category": str(raw.get("category") or "434"),
            },
        )


def _validate_api_payload(payload: dict[str, Any]) -> None:
    code = payload.get("code")
    if code is None:
        return
    if str(code).strip().lower() in {"0", "success"}:
        return
    message = str(payload.get("message") or "未知错误").strip()
    if "頻繁" in message or "频繁" in message:
        raise RuntimeError("M-Team 请求过于频繁，请稍后重试。")
    raise RuntimeError(f"M-Team API 返回错误：{message}")


def _to_int(value: object) -> int:
    try:
        return int(str(value or "0"))
    except ValueError:
        return 0


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _promotion_text(value: object) -> str | None:
    discount = str(value or "").strip().upper()
    labels = {
        "FREE": "FREE",
        "_2X_FREE": "2X FREE",
        "PERCENT_50": "50%",
        "_2X_PERCENT_50": "2X 50%",
        "PERCENT_70": "70%",
        "_2X": "2X",
    }
    return labels.get(discount)
