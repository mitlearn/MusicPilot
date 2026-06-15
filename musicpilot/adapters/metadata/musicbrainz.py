from __future__ import annotations

import httpx

from musicpilot.ports.metadata import TrackMetadata


class MusicBrainzProvider:
    def __init__(self, *, user_agent: str, client: httpx.AsyncClient | None = None) -> None:
        self.user_agent = user_agent
        self._client = client or httpx.AsyncClient(
            base_url="https://musicbrainz.org/ws/2",
            timeout=20,
            headers={"User-Agent": user_agent},
        )
        self._owns_client = client is None

    @property
    def name(self) -> str:
        return "musicbrainz"

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def lookup(self, *, title: str, artist: str | None = None) -> TrackMetadata | None:
        query = f'recording:"{title}"'
        if artist:
            query += f' AND artist:"{artist}"'
        response = await self._client.get(
            "/recording",
            params={"query": query, "fmt": "json", "limit": 1},
        )
        response.raise_for_status()
        recordings = response.json().get("recordings", [])
        if not recordings:
            return None
        item = recordings[0]
        artist_credit = item.get("artist-credit") or []
        artist_name = artist_credit[0].get("name") if artist_credit else artist
        releases = item.get("releases") or []
        first_release = releases[0] if releases else {}
        return TrackMetadata(
            title=item.get("title", title),
            artist=artist_name,
            album=first_release.get("title"),
            year=_parse_year(first_release.get("date")),
            extra={"musicbrainz_recording_id": item.get("id", "")},
        )


def _parse_year(date_value: str | None) -> int | None:
    if not date_value:
        return None
    try:
        return int(date_value[:4])
    except ValueError:
        return None
