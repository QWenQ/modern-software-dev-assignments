from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import httpx

from week3.server.auth import LocalBearerTokenService
from week3.server.config import Settings
from week3.server.main import create_app


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


class FakeSpotifyClient:
    async def aclose(self) -> None:
        return None

    async def search_tracks(self, query: str, *, limit: int) -> tuple[list[dict[str, Any]], str | None]:
        return (
            [
                {
                    "id": "track-1",
                    "name": f"{query} Song",
                    "artists": ["Example Artist"],
                    "album": "Example Album",
                    "urls": {
                        "spotify": "https://open.spotify.com/track/track-1",
                        "album": "https://open.spotify.com/album/album-1",
                    },
                    "popularity": 77,
                    "duration_ms": 215000,
                    "duration": "3:35",
                }
            ][:limit],
            None,
        )

    async def resolve_artist(self, artist_name_or_id: str) -> tuple[dict[str, Any] | None, str | None]:
        if artist_name_or_id == "missing":
            return None, "No artist found matching 'missing'."
        return (
            {
                "id": "artist-1",
                "name": "Example Artist",
                "genres": ["indie rock"],
                "followers": {"total": 123456},
                "external_urls": {"spotify": "https://open.spotify.com/artist/artist-1"},
            },
            "Input did not match Spotify artist ID format, so the server used artist search.",
        )

    async def get_artist_top_tracks(
        self,
        artist_id: str,
        *,
        limit: int = 5,
    ) -> tuple[list[dict[str, Any]], str | None]:
        return (
            [
                {
                    "id": "top-track-1",
                    "name": "Top Track",
                    "artists": ["Example Artist"],
                    "album": "Top Album",
                    "urls": {
                        "spotify": "https://open.spotify.com/track/top-track-1",
                        "album": "https://open.spotify.com/album/top-album-1",
                    },
                    "popularity": 88,
                    "duration_ms": 205000,
                    "duration": "3:25",
                }
            ][:limit],
            None,
        )


@asynccontextmanager
async def app_client(app):
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


async def get_access_token(client: httpx.AsyncClient) -> str:
    response = await client.get("/auth/token")
    assert response.status_code == 200
    return response.json()["access_token"]


def test_mcp_requires_bearer_token() -> None:
    async def run_test() -> None:
        app = create_app(make_settings(), spotify_client=FakeSpotifyClient())
        async with app_client(app) as client:
            response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert response.status_code == 401
        assert "/auth/login" in response.json()["detail"]

    asyncio.run(run_test())


def test_mcp_rejects_wrong_token_audience() -> None:
    async def run_test() -> None:
        settings = make_settings()
        app = create_app(settings, spotify_client=FakeSpotifyClient())
        token_service = LocalBearerTokenService(settings)
        token_payload = token_service.issue_token(subject="local-user", audience="wrong-audience")
        async with app_client(app) as client:
            response = await client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {token_payload['access_token']}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            )
        assert response.status_code == 401
        assert "audience is invalid" in response.json()["detail"]

    asyncio.run(run_test())


def test_tools_list_returns_both_spotify_tools() -> None:
    async def run_test() -> None:
        app = create_app(make_settings(), spotify_client=FakeSpotifyClient())
        async with app_client(app) as client:
            token = await get_access_token(client)
            response = await client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {token}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
        assert response.status_code == 200
        tools = response.json()["result"]["tools"]
        assert [tool["name"] for tool in tools] == ["search_tracks", "get_artist_info"]

    asyncio.run(run_test())


def test_search_tracks_validation_error_is_reported_as_tool_error() -> None:
    async def run_test() -> None:
        app = create_app(make_settings(), spotify_client=FakeSpotifyClient())
        async with app_client(app) as client:
            token = await get_access_token(client)
            response = await client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "search_tracks", "arguments": {"query": "   ", "limit": 10}},
                },
            )
        payload = response.json()["result"]
        assert payload["isError"] is True
        assert "query must not be empty" in payload["content"][0]["text"]

    asyncio.run(run_test())


def test_get_artist_info_returns_artist_summary_and_top_tracks() -> None:
    async def run_test() -> None:
        app = create_app(make_settings(), spotify_client=FakeSpotifyClient())
        async with app_client(app) as client:
            token = await get_access_token(client)
            response = await client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "get_artist_info", "arguments": {"artist_name_or_id": "Radiohead"}},
                },
            )
        payload = response.json()["result"]
        assert payload["isError"] is False
        assert payload["structuredContent"]["artist"]["name"] == "Example Artist"
        assert len(payload["structuredContent"]["top_tracks"]) == 1
        assert "artist search" in payload["structuredContent"]["message"]

    asyncio.run(run_test())
