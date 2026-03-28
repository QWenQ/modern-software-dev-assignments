# Spotify MCP Server

This week implements a local HTTP MCP server that wraps the Spotify Web API with two tools:

- `search_tracks`
- `get_artist_info`

The server runs on port `8000` by default, uses Spotify client credentials for upstream API access, and protects the MCP HTTP endpoint with its own local bearer tokens. Those bearer tokens are validated locally, including audience checks, and are never forwarded to Spotify.

## Endpoints used

- `GET /v1/search`
- `GET /v1/artists/{id}`
- `GET /v1/artists/{id}/top-tracks`

## Project layout

```text
week3/
  __init__.py
  README.md
  requirements.txt
  server/
    auth.py
    config.py
    errors.py
    main.py
    mcp.py
    spotify.py
  tests/
    test_app.py
    test_spotify.py
```

## Prerequisites

- Python `3.10+`
- A Spotify developer app with `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`

Create Spotify credentials here:

- <https://developer.spotify.com/dashboard>

## Environment variables

Required:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`

Recommended:

- `MCP_AUTH_SECRET`: secret used to sign local bearer tokens

Optional:

- `MCP_HOST`: default `127.0.0.1`
- `MCP_PORT`: default `8000`
- `MCP_PUBLIC_BASE_URL`: default `http://127.0.0.1:8000`
- `MCP_TOKEN_AUDIENCE`: default `spotify-mcp-server`
- `MCP_TOKEN_TTL_SECONDS`: default `3600`
- `SPOTIFY_MARKET`: default `US`
- `SPOTIFY_TIMEOUT_SECONDS`: default `10`
- `SPOTIFY_MIN_REQUEST_INTERVAL_SECONDS`: default `0.05`

## Install

Using the repo-wide Poetry environment:

```bash
poetry install --no-interaction
```

Or with pip just for this assignment:

```bash
pip install -r week3/requirements.txt
```

## Run

From the repository root:

```bash
export SPOTIFY_CLIENT_ID="your-client-id"
export SPOTIFY_CLIENT_SECRET="your-client-secret"
export MCP_AUTH_SECRET="replace-this-with-a-random-string"
uvicorn week3.server.main:app --host 127.0.0.1 --port 8000
```

Useful URLs:

- MCP endpoint: `http://127.0.0.1:8000/mcp`
- Auth login page: `http://127.0.0.1:8000/auth/login`
- OAuth metadata: `http://127.0.0.1:8000/.well-known/oauth-authorization-server`
- API docs: `http://127.0.0.1:8000/docs`

## Authentication flow

1. Open `http://127.0.0.1:8000/auth/login`.
2. Click `Issue local bearer token`.
3. Copy the returned `access_token`.
4. Configure your MCP client to send `Authorization: Bearer <access_token>` to `http://127.0.0.1:8000/mcp`.

You can also mint a token by command line:

```bash
curl "http://127.0.0.1:8000/auth/token?subject=local-user&audience=spotify-mcp-server"
```

The bearer token is only for this MCP server. Spotify calls use a separate server-managed token created with the Spotify client credentials flow.

## Tool reference

### `search_tracks`

Parameters:

- `query`: non-empty string
- `limit`: integer `1-50`, default `10`

Returns:

- Track name
- Artists
- Album
- URLs
- Popularity
- Duration

Example tool arguments:

```json
{
  "query": "Paranoid Android",
  "limit": 5
}
```

Example structured result shape:

```json
{
  "query": "Paranoid Android",
  "limit": 5,
  "message": "Found 5 track(s).",
  "tracks": [
    {
      "id": "spotify-track-id",
      "name": "Paranoid Android",
      "artists": ["Radiohead"],
      "album": "OK Computer",
      "urls": {
        "spotify": "https://open.spotify.com/track/...",
        "album": "https://open.spotify.com/album/..."
      },
      "popularity": 74,
      "duration_ms": 387000,
      "duration": "6:27"
    }
  ]
}
```

### `get_artist_info`

Parameters:

- `artist_name_or_id`: Spotify artist ID or artist name

Returns:

- Artist name
- Genres
- Followers
- Top 5 tracks
- URLs

Example tool arguments:

```json
{
  "artist_name_or_id": "Radiohead"
}
```

Example structured result shape:

```json
{
  "artist_name_or_id": "Radiohead",
  "message": "Input did not match Spotify artist ID format, so the server used artist search.",
  "artist": {
    "id": "spotify-artist-id",
    "name": "Radiohead",
    "genres": ["alternative rock", "art rock"],
    "followers": 12345678,
    "urls": {
      "spotify": "https://open.spotify.com/artist/..."
    }
  },
  "top_tracks": [
    {
      "id": "spotify-track-id",
      "name": "Creep",
      "artists": ["Radiohead"],
      "album": "Pablo Honey",
      "urls": {
        "spotify": "https://open.spotify.com/track/...",
        "album": "https://open.spotify.com/album/..."
      },
      "popularity": 84,
      "duration_ms": 238000,
      "duration": "3:58"
    }
  ]
}
```

## Example invocation flow

In a client such as MCP Inspector or any MCP-aware HTTP client:

1. Add a remote MCP server pointing to `http://127.0.0.1:8000/mcp`.
2. Set the HTTP header `Authorization: Bearer <token-from-/auth/login>`.
3. Initialize the connection.
4. Open the tool list and choose `search_tracks`.
5. Enter:

```json
{"query":"Paranoid Android","limit":5}
```

6. Run the tool and inspect the returned tracks.
7. Choose `get_artist_info`.
8. Enter:

```json
{"artist_name_or_id":"Radiohead"}
```

9. Run the tool to get artist metadata plus the top 5 tracks.

You can also test the MCP endpoint directly with JSON-RPC:

```bash
TOKEN="$(curl -s 'http://127.0.0.1:8000/auth/token?subject=local-user&audience=spotify-mcp-server' | python -c 'import json,sys; print(json.load(sys.stdin)[\"access_token\"])')"

curl -s http://127.0.0.1:8000/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_tracks","arguments":{"query":"Paranoid Android","limit":3}}}'
```

## Resilience implemented

- HTTP failures are wrapped with descriptive error messages.
- Spotify timeouts use a `10s` client timeout and return explicit timeout errors.
- Empty results return empty lists plus a helpful message instead of crashing.
- Requests are spaced by `50ms` by default to be gentle with the upstream API.
- Spotify `429` responses are detected and surfaced with retry guidance.
- `search_tracks` validates non-empty queries and `limit` range `1-50`.
- `get_artist_info` validates non-empty input and falls back to artist search when the input is not a valid Spotify artist ID.
- Spotify client credentials tokens refresh automatically before expiry and retry once on upstream `401`.
- MCP bearer token failures tell the caller to visit `/auth/login`.
