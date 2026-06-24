from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

SPOTIFY_PLAYLIST_SCOPES = (
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-read-private",
)


class SpotifyAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class SpotifyClient:
    accounts_base_url = "https://accounts.spotify.com"
    api_base_url = "https://api.spotify.com/v1"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=30, follow_redirects=True)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def authorization_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        state: str,
        scopes: tuple[str, ...] = SPOTIFY_PLAYLIST_SCOPES,
    ) -> str:
        params = {
            "response_type": "code",
            "client_id": client_id,
            "scope": " ".join(scopes),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{self.accounts_base_url}/authorize?{urlencode(params)}"

    async def exchange_code(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code: str,
    ) -> dict[str, Any]:
        response = await self._client.post(
            f"{self.accounts_base_url}/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=(client_id, client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return _token_response(response)

    async def refresh_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        response = await self._client.post(
            f"{self.accounts_base_url}/api/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(client_id, client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return _token_response(response)

    async def profile(self, access_token: str) -> dict[str, Any]:
        response = await self._client.get(
            f"{self.api_base_url}/me",
            headers=_auth_headers(access_token),
        )
        if response.status_code == 403:
            raise SpotifyAPIError(
                response.status_code,
                _api_error_message(
                    response,
                    (
                        "Spotify refused /me with 403. Reauthorize with the "
                        "user-read-private scope and make sure the Spotify account is "
                        "added to the app's User Management allowlist while the app is "
                        "in development mode."
                    ),
                ),
            )
        _raise_for_api_error(response)
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def playlists(self, access_token: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        url = f"{self.api_base_url}/me/playlists"
        params: dict[str, object] = {"limit": 50, "offset": 0}
        while True:
            response = await self._client.get(
                url,
                headers=_auth_headers(access_token),
                params=params,
            )
            if response.status_code == 403:
                raise SpotifyAPIError(
                    response.status_code,
                    _api_error_message(
                        response,
                        (
                            "Spotify refused playlist access with 403. Make sure the "
                            "authorized Spotify account is added to the app's User "
                            "Management allowlist while the app is in development mode."
                        ),
                    ),
                )
            _raise_for_api_error(response)
            payload = response.json()
            page_items = payload.get("items", []) if isinstance(payload, dict) else []
            if not isinstance(page_items, list) or not page_items:
                break
            items.extend(item for item in page_items if isinstance(item, dict))
            next_url = payload.get("next") if isinstance(payload, dict) else None
            if not next_url:
                break
            params["offset"] = int(params["offset"]) + int(params["limit"])
        return items

    async def playlist_tracks(self, access_token: str, playlist_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        url = f"{self.api_base_url}/playlists/{playlist_id}/tracks"
        params: dict[str, object] = {
            "limit": 50,
            "offset": 0,
            "fields": (
                "items(added_at,track(id,name,duration_ms,external_ids,"
                "album(name,images),artists(name))),next"
            ),
        }
        while True:
            response = await self._client.get(
                url,
                headers=_auth_headers(access_token),
                params=params,
            )
            if response.status_code == 403:
                raise SpotifyAPIError(
                    response.status_code,
                    _api_error_message(
                        response,
                        (
                            "Spotify refused playlist track access with 403. Make sure the "
                            "authorized Spotify account is added to the app's User "
                            "Management allowlist while the app is in development mode."
                        ),
                    ),
                )
            _raise_for_api_error(response)
            payload = response.json()
            page_items = payload.get("items", []) if isinstance(payload, dict) else []
            if not isinstance(page_items, list) or not page_items:
                break
            items.extend(item for item in page_items if isinstance(item, dict))
            next_url = payload.get("next") if isinstance(payload, dict) else None
            if not next_url:
                break
            params["offset"] = int(params["offset"]) + int(params["limit"])
        return items


def token_expiry(expires_in: object) -> datetime:
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        seconds = 3600
    return datetime.now(UTC) + timedelta(seconds=max(60, seconds - 60))


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=180)


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _token_response(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = {"error": response.text}
    if response.is_error:
        error = payload.get("error") if isinstance(payload, dict) else None
        detail = payload.get("error_description") if isinstance(payload, dict) else None
        message = ": ".join(str(item) for item in (error, detail) if item)
        raise RuntimeError(message or f"Spotify token request failed: {response.status_code}")
    return payload if isinstance(payload, dict) else {}


def _raise_for_api_error(response: httpx.Response) -> None:
    if not response.is_error:
        return
    raise SpotifyAPIError(
        response.status_code,
        _api_error_message(response, f"Spotify API request failed: {response.status_code}"),
    )


def _api_error_message(response: httpx.Response, fallback: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return f"{fallback} Spotify response: {message}"
        if isinstance(error, str):
            description = payload.get("error_description")
            values = [error, description]
            detail = ": ".join(str(item) for item in values if item)
            if detail:
                return f"{fallback} Spotify response: {detail}"
    if response.text:
        return f"{fallback} Spotify response: {response.text[:500]}"
    return fallback
