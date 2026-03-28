from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parents[1]

if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")
    load_dotenv()


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return int(raw_value)


def _get_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return float(raw_value)


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    host: str
    port: int
    public_base_url: str
    spotify_client_id: str
    spotify_client_secret: str
    spotify_market: str
    spotify_timeout_seconds: float
    spotify_min_request_interval_seconds: float
    spotify_accounts_base_url: str
    spotify_api_base_url: str
    mcp_auth_secret: str
    mcp_token_audience: str
    mcp_token_ttl_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = _get_int_env("MCP_PORT", 8000)
    public_base_url = os.getenv("MCP_PUBLIC_BASE_URL", f"http://127.0.0.1:{port}")

    return Settings(
        app_name=os.getenv("MCP_APP_NAME", "Spotify MCP Server"),
        app_version=os.getenv("MCP_APP_VERSION", "0.1.0"),
        host=host,
        port=port,
        public_base_url=public_base_url.rstrip("/"),
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", ""),
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ""),
        spotify_market=os.getenv("SPOTIFY_MARKET", "US"),
        spotify_timeout_seconds=_get_float_env("SPOTIFY_TIMEOUT_SECONDS", 10.0),
        spotify_min_request_interval_seconds=_get_float_env(
            "SPOTIFY_MIN_REQUEST_INTERVAL_SECONDS", 0.05
        ),
        spotify_accounts_base_url=os.getenv(
            "SPOTIFY_ACCOUNTS_BASE_URL", "https://accounts.spotify.com"
        ).rstrip("/"),
        spotify_api_base_url=os.getenv("SPOTIFY_API_BASE_URL", "https://api.spotify.com").rstrip(
            "/"
        ),
        mcp_auth_secret=os.getenv("MCP_AUTH_SECRET", "change-me-for-local-dev"),
        mcp_token_audience=os.getenv("MCP_TOKEN_AUDIENCE", "spotify-mcp-server"),
        mcp_token_ttl_seconds=_get_int_env("MCP_TOKEN_TTL_SECONDS", 3600),
    )
