from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from .auth import LocalBearerTokenService, TokenClaims, require_bearer_token
from .config import Settings, get_settings
from .mcp import build_initialize_result, build_tools_list, execute_tool
from .spotify import SpotifyClient


class TokenRequest(BaseModel):
    subject: str = Field(default="local-user")
    audience: str | None = Field(default=None)
    expires_in: int | None = Field(default=None, ge=60, le=86400)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("subject must not be empty")
        return value.strip()


def create_app(
    settings: Settings | None = None,
    *,
    spotify_client: SpotifyClient | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = resolved_settings
        app.state.token_service = LocalBearerTokenService(resolved_settings)
        client = spotify_client or SpotifyClient(resolved_settings)
        app.state.spotify_client = client
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(title=resolved_settings.app_name, version=resolved_settings.app_version, lifespan=lifespan)

    @app.get("/", tags=["system"])
    async def index() -> dict[str, Any]:
        settings = app.state.settings
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "mcp_endpoint": f"{settings.public_base_url}/mcp",
            "auth_login": f"{settings.public_base_url}/auth/login",
            "tools": ["search_tracks", "get_artist_info"],
        }

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/.well-known/oauth-authorization-server", tags=["auth"])
    async def oauth_authorization_server_metadata() -> dict[str, Any]:
        settings = app.state.settings
        return {
            "issuer": settings.public_base_url,
            "authorization_endpoint": f"{settings.public_base_url}/auth/login",
            "token_endpoint": f"{settings.public_base_url}/auth/token",
            "token_endpoint_auth_methods_supported": ["none"],
            "response_types_supported": ["token"],
            "grant_types_supported": ["implicit", "client_credentials"],
        }

    @app.get("/auth/login", response_class=HTMLResponse, tags=["auth"])
    async def auth_login_page() -> str:
        settings = app.state.settings
        audience = settings.mcp_token_audience
        return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{settings.app_name} Login</title>
    <style>
      body {{
        font-family: ui-sans-serif, system-ui, sans-serif;
        max-width: 840px;
        margin: 48px auto;
        padding: 0 20px;
        line-height: 1.5;
      }}
      code, textarea {{
        font-family: ui-monospace, monospace;
      }}
      textarea {{
        width: 100%;
        min-height: 180px;
      }}
      button {{
        padding: 10px 16px;
        font-size: 16px;
      }}
    </style>
  </head>
  <body>
    <h1>{settings.app_name}</h1>
    <p>This local page mints a bearer token for the MCP HTTP transport. The token audience is <code>{audience}</code>.</p>
    <p>The server validates this token locally and never forwards it to Spotify. Spotify requests use a separate server-managed client credentials token.</p>
    <button id="issue-token">Issue local bearer token</button>
    <p>Then use the returned token as <code>Authorization: Bearer &lt;token&gt;</code> when calling <code>{settings.public_base_url}/mcp</code>.</p>
    <textarea id="token-output" readonly>Click the button to create a token.</textarea>
    <script>
      document.getElementById("issue-token").addEventListener("click", async () => {{
        const response = await fetch("/auth/token?subject=local-user&audience={audience}");
        const payload = await response.json();
        document.getElementById("token-output").value = JSON.stringify(payload, null, 2);
      }});
    </script>
  </body>
</html>
        """.strip()

    @app.get("/auth/token", tags=["auth"])
    async def issue_token_from_query(
        subject: str = "local-user",
        audience: str | None = None,
        expires_in: int | None = None,
    ) -> dict[str, Any]:
        payload = TokenRequest(subject=subject, audience=audience, expires_in=expires_in)
        return _issue_token(app, payload)

    @app.post("/auth/token", tags=["auth"])
    async def issue_token_from_json(payload: TokenRequest) -> dict[str, Any]:
        return _issue_token(app, payload)

    @app.post("/mcp", tags=["mcp"])
    async def mcp_endpoint(
        request: Request,
        _: TokenClaims = Depends(require_bearer_token),
    ) -> Response:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content=_jsonrpc_error(None, -32700, "Invalid JSON payload."),
            )

        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content=_jsonrpc_error(None, -32600, "MCP server expects a single JSON-RPC object."),
            )

        response = await _handle_jsonrpc_message(app, body)
        if response is None:
            return Response(status_code=202)
        return JSONResponse(content=response)

    return app


def _issue_token(app: FastAPI, payload: TokenRequest) -> dict[str, Any]:
    settings = app.state.settings
    audience = payload.audience or settings.mcp_token_audience
    if audience != settings.mcp_token_audience:
        raise HTTPException(
            status_code=400,
            detail=(
                "Requested audience is not allowed for this local server. "
                f"Use {settings.mcp_token_audience!r}."
            ),
        )
    return app.state.token_service.issue_token(
        subject=payload.subject,
        audience=audience,
        expires_in_seconds=payload.expires_in,
    )


async def _handle_jsonrpc_message(app: FastAPI, body: dict[str, Any]) -> dict[str, Any] | None:
    is_notification = "id" not in body
    request_id = body.get("id")
    if body.get("jsonrpc") != "2.0":
        return None if is_notification else _jsonrpc_error(request_id, -32600, "jsonrpc must be '2.0'.")

    method = body.get("method")
    params = body.get("params")
    if not isinstance(method, str) or not method:
        return (
            None
            if is_notification
            else _jsonrpc_error(request_id, -32600, "method must be a non-empty string.")
        )
    if params is not None and not isinstance(params, dict):
        return (
            None
            if is_notification
            else _jsonrpc_error(request_id, -32602, "params must be an object when provided.")
        )

    if method == "notifications/initialized":
        return None
    if method == "ping":
        return None if is_notification else _jsonrpc_result(request_id, {})
    if method == "initialize":
        return None if is_notification else _jsonrpc_result(request_id, build_initialize_result(app))
    if method == "tools/list":
        return None if is_notification else _jsonrpc_result(request_id, build_tools_list())
    if method == "tools/call":
        tool_name = (params or {}).get("name")
        arguments = (params or {}).get("arguments")
        if not isinstance(tool_name, str) or not tool_name:
            return (
                None
                if is_notification
                else _jsonrpc_error(request_id, -32602, "tools/call requires a non-empty 'name'.")
            )
        if arguments is not None and not isinstance(arguments, dict):
            return (
                None
                if is_notification
                else _jsonrpc_error(request_id, -32602, "'arguments' must be an object when provided.")
            )
        spotify_client: SpotifyClient = app.state.spotify_client
        result = await execute_tool(tool_name, arguments, spotify_client)
        return None if is_notification else _jsonrpc_result(request_id, result)

    return None if is_notification else _jsonrpc_error(request_id, -32601, f"Method {method!r} is not supported.")


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


app = create_app()
