from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from .config import Settings
from .errors import SpotifyAPIError, SpotifyAuthError, SpotifyRateLimitError


SPOTIFY_ARTIST_ID_LENGTH = 22


def is_spotify_artist_id(value: str) -> bool:
    candidate = value.strip()
    return len(candidate) == SPOTIFY_ARTIST_ID_LENGTH and candidate.isalnum()


def format_duration(duration_ms: int | None) -> str | None:
    if duration_ms is None:
        return None
    total_seconds = duration_ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


class SpotifyClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(timeout=settings.spotify_timeout_seconds)
        self._owns_client = http_client is None
        self._token_lock = asyncio.Lock()
        self._rate_limit_lock = asyncio.Lock()
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._last_request_started_at = 0.0

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_tracks(self, query: str, *, limit: int) -> tuple[list[dict[str, Any]], str | None]:
        data = await self._api_get(
            "/v1/search",
            params={"q": query, "type": "track", "limit": limit},
        )
        items = data.get("tracks", {}).get("items", [])
        if not items:
            return [], f"No tracks found for query {query!r}."
        return [self._format_track(item) for item in items], None

    async def resolve_artist(self, artist_name_or_id: str) -> tuple[dict[str, Any] | None, str | None]:
        candidate = artist_name_or_id.strip()
        if is_spotify_artist_id(candidate):
            artist = await self.get_artist(candidate)
            return artist, "Resolved using the provided Spotify artist ID."

        data = await self._api_get(
            "/v1/search",
            params={"q": candidate, "type": "artist", "limit": 1},
        )
        items = data.get("artists", {}).get("items", [])
        if not items:
            return None, f"No artist found matching {candidate!r}."
        return items[0], "Input did not match Spotify artist ID format, so the server used artist search."

    async def get_artist(self, artist_id: str) -> dict[str, Any]:
        return await self._api_get(f"/v1/artists/{artist_id}")

    async def get_artist_top_tracks(
        self,
        artist_id: str,
        *,
        limit: int = 5,
    ) -> tuple[list[dict[str, Any]], str | None]:
        data = await self._api_get(
            f"/v1/artists/{artist_id}/top-tracks",
            params={"market": self._settings.spotify_market},
        )
        items = data.get("tracks", [])[:limit]
        if not items:
            return [], "Spotify returned no top tracks for this artist in the configured market."
        return [self._format_track(item) for item in items], None

    async def _api_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        retry_on_auth_error: bool = True,
    ) -> dict[str, Any]:
        access_token = await self._get_access_token()
        await self._respect_rate_limit()
        url = f"{self._settings.spotify_api_base_url}{path}"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await self._client.get(url, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise SpotifyAPIError(
                f"Spotify request timed out after {self._settings.spotify_timeout_seconds:g} seconds."
            ) from exc
        except httpx.HTTPError as exc:
            raise SpotifyAPIError(f"Spotify request failed before receiving a response: {exc}") from exc

        if response.status_code == 401 and retry_on_auth_error:
            await self._refresh_access_token(force=True)
            return await self._api_get(path, params=params, retry_on_auth_error=False)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            detail = "Spotify rate limit reached (HTTP 429)."
            if retry_after:
                detail += f" Retry after {retry_after} second(s)."
            raise SpotifyRateLimitError(detail)

        if response.status_code >= 400:
            detail = self._extract_error_message(response)
            raise SpotifyAPIError(
                f"Spotify API request failed for {path} with HTTP {response.status_code}: {detail}"
            )

        return response.json()

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expires_at:
            return self._access_token
        await self._refresh_access_token(force=False)
        if not self._access_token:  # pragma: no cover - defensive branch
            raise SpotifyAuthError("Spotify access token is unavailable after refresh.")
        return self._access_token

    async def _refresh_access_token(self, *, force: bool) -> None:
        async with self._token_lock:
            if (
                not force
                and self._access_token
                and time.time() < self._access_token_expires_at
            ):
                return

            if not self._settings.spotify_client_id or not self._settings.spotify_client_secret:
                raise SpotifyAuthError(
                    "Spotify credentials are missing. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."
                )

            url = f"{self._settings.spotify_accounts_base_url}/api/token"
            try:
                response = await self._client.post(
                    url,
                    data={"grant_type": "client_credentials"},
                    auth=(self._settings.spotify_client_id, self._settings.spotify_client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except httpx.TimeoutException as exc:
                raise SpotifyAuthError(
                    f"Spotify token refresh timed out after {self._settings.spotify_timeout_seconds:g} seconds."
                ) from exc
            except httpx.HTTPError as exc:
                raise SpotifyAuthError(f"Spotify token refresh failed before response: {exc}") from exc

            if response.status_code >= 400:
                detail = self._extract_error_message(response)
                raise SpotifyAuthError(
                    "Spotify authentication failed. Check SPOTIFY_CLIENT_ID and "
                    f"SPOTIFY_CLIENT_SECRET. Spotify said: {detail}"
                )

            payload = response.json()
            access_token = payload.get("access_token")
            expires_in = int(payload.get("expires_in", 3600))
            if not access_token:
                raise SpotifyAuthError("Spotify token response did not include access_token.")

            self._access_token = str(access_token)
            self._access_token_expires_at = time.time() + max(expires_in - 30, 1)

    async def _respect_rate_limit(self) -> None:
        async with self._rate_limit_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_started_at
            minimum_gap = self._settings.spotify_min_request_interval_seconds
            if elapsed < minimum_gap:
                await asyncio.sleep(minimum_gap - elapsed)
            self._last_request_started_at = time.monotonic()

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text or "No response body."

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if message:
                    return str(message)
            if isinstance(error, str):
                return error
            message = payload.get("message")
            if message:
                return str(message)
        return "Unknown Spotify error."

    @staticmethod
    def _format_track(item: dict[str, Any]) -> dict[str, Any]:
        album = item.get("album") or {}
        duration_ms = item.get("duration_ms")
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "artists": [artist.get("name") for artist in item.get("artists", []) if artist.get("name")],
            "album": album.get("name"),
            "urls": {
                "spotify": (item.get("external_urls") or {}).get("spotify"),
                "album": (album.get("external_urls") or {}).get("spotify"),
            },
            "popularity": item.get("popularity"),
            "duration_ms": duration_ms,
            "duration": format_duration(duration_ms),
        }
