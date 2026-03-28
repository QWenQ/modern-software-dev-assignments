from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError, field_validator

from .errors import SpotifyAPIError
from .spotify import SpotifyClient


class SearchTracksInput(BaseModel):
    query: str = Field(..., description="Track search query.")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of tracks to return.")

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value.strip()


class GetArtistInfoInput(BaseModel):
    artist_name_or_id: str = Field(
        ...,
        description="Spotify artist ID or artist name to search for.",
    )

    @field_validator("artist_name_or_id")
    @classmethod
    def validate_artist_input(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("artist_name_or_id must not be empty")
        return value.strip()


def build_initialize_result(app: FastAPI) -> dict[str, Any]:
    settings = app.state.settings
    return {
        "protocolVersion": "2025-06-18",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": settings.app_name, "version": settings.app_version},
        "instructions": (
            f"Authenticate with a bearer token issued by {settings.public_base_url}/auth/token, "
            "then call tools/list and tools/call."
        ),
    }


def build_tools_list() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": "search_tracks",
                "description": "Search Spotify tracks by query string.",
                "inputSchema": SearchTracksInput.model_json_schema(),
            },
            {
                "name": "get_artist_info",
                "description": "Get Spotify artist details and top tracks by artist name or Spotify ID.",
                "inputSchema": GetArtistInfoInput.model_json_schema(),
            },
        ]
    }


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any] | None,
    spotify_client: SpotifyClient,
) -> dict[str, Any]:
    try:
        if tool_name == "search_tracks":
            payload = SearchTracksInput.model_validate(arguments or {})
            tracks, message = await spotify_client.search_tracks(payload.query, limit=payload.limit)
            structured = {
                "query": payload.query,
                "limit": payload.limit,
                "message": message or f"Found {len(tracks)} track(s).",
                "tracks": tracks,
            }
            return _tool_success(structured["message"], structured)

        if tool_name == "get_artist_info":
            payload = GetArtistInfoInput.model_validate(arguments or {})
            artist, resolution_message = await spotify_client.resolve_artist(payload.artist_name_or_id)
            if artist is None:
                structured = {
                    "artist_name_or_id": payload.artist_name_or_id,
                    "message": resolution_message or "Artist not found.",
                    "artist": None,
                    "top_tracks": [],
                }
                return _tool_success(structured["message"], structured)

            top_tracks, top_track_message = await spotify_client.get_artist_top_tracks(
                str(artist.get("id") or "")
            )
            artist_summary = {
                "id": artist.get("id"),
                "name": artist.get("name"),
                "genres": artist.get("genres") or [],
                "followers": (artist.get("followers") or {}).get("total", 0),
                "urls": artist.get("external_urls") or {},
            }
            messages = [message for message in [resolution_message, top_track_message] if message]
            structured = {
                "artist_name_or_id": payload.artist_name_or_id,
                "message": " ".join(messages) or f"Fetched artist info for {artist_summary['name']}.",
                "artist": artist_summary,
                "top_tracks": top_tracks,
            }
            return _tool_success(structured["message"], structured)

    except ValidationError as exc:
        message = _validation_message(exc)
        return _tool_error(f"Invalid tool arguments: {message}")
    except SpotifyAPIError as exc:
        return _tool_error(str(exc))

    return _tool_error(f"Unknown tool {tool_name!r}.")


def _validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "unknown validation error"
    first = errors[0]
    return str(first.get("msg", "unknown validation error"))


def _tool_success(text: str, structured_content: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured_content,
        "isError": False,
    }


def _tool_error(text: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": True,
    }
