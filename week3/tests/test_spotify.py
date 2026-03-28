from __future__ import annotations

import asyncio

import httpx
import pytest

from week3.server.config import Settings
from week3.server.errors import SpotifyRateLimitError
from week3.server.spotify import SpotifyClient


def make_settings() -> Settings:
    return Settings(
        app_name="Spotify MCP Server",
        app_version="0.1.0",
        host="127.0.0.1",
        port=8000,
        public_base_url="http://127.0.0.1:8000",
        spotify_client_id="spotify-client-id",
        spotify_client_secret="spotify-client-secret",
        spotify_market="US",
        spotify_timeout_seconds=10.0,
        spotify_min_request_interval_seconds=0.0,
        spotify_accounts_base_url="https://accounts.spotify.com",
        spotify_api_base_url="https://api.spotify.com",
        mcp_auth_secret="test-secret",
        mcp_token_audience="spotify-mcp-server",
        mcp_token_ttl_seconds=3600,
    )


def test_spotify_client_searches_for_artist_name_when_input_is_not_an_id() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "spotify-token", "expires_in": 3600})
        if request.url.path == "/v1/search":
            assert request.url.params["type"] == "artist"
            assert request.url.params["limit"] == "1"
            assert request.url.params["q"] == "Radiohead"
            return httpx.Response(
                200,
                json={
                    "artists": {
                        "items": [
                            {
                                "id": "artist-1",
                                "name": "Radiohead",
                                "genres": ["alternative rock"],
                                "followers": {"total": 99},
                                "external_urls": {"spotify": "https://open.spotify.com/artist/artist-1"},
                            }
                        ]
                    }
                },
            )
        raise AssertionError(f"Unexpected request to {request.url}")

    async def run_test() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            spotify_client = SpotifyClient(make_settings(), http_client=client)
            artist, message = await spotify_client.resolve_artist("Radiohead")
            assert artist is not None
            assert artist["name"] == "Radiohead"
            assert "artist search" in (message or "")

    asyncio.run(run_test())
    assert [request.url.path for request in requests] == ["/api/token", "/v1/search"]


def test_spotify_client_surfaces_rate_limit_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "spotify-token", "expires_in": 3600})
        if request.url.path == "/v1/search":
            return httpx.Response(429, headers={"Retry-After": "3"}, json={"error": {"message": "slow down"}})
        raise AssertionError(f"Unexpected request to {request.url}")

    async def run_test() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            spotify_client = SpotifyClient(make_settings(), http_client=client)
            with pytest.raises(SpotifyRateLimitError) as exc_info:
                await spotify_client.search_tracks("Paranoid Android", limit=5)
            assert "HTTP 429" in str(exc_info.value)
            assert "Retry after 3" in str(exc_info.value)

    asyncio.run(run_test())
