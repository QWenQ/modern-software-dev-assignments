# Action Item Extractor

Action Item Extractor is a small FastAPI application that turns free-form notes into structured action items, stores notes and extracted tasks in SQLite, and serves a minimal browser UI for interacting with the API.

The project supports two extraction flows:

- A heuristic flow based on bullet points, checkboxes, and simple imperative-sentence detection
- An Ollama-backed LLM flow for richer extraction when a local model is available

The backend also exposes note management endpoints, action item status updates, consistent JSON error responses, and an automated test suite.

## Features

- Create, list, and retrieve notes
- Extract action items from free-form text
- Save extracted action items with or without saving the original note
- Mark action items as done or not done
- Filter action items by note
- Use a minimal built-in frontend at `/`
- Run heuristic extraction even when the LLM dependency is unavailable
- Call a dedicated LLM endpoint when Ollama is configured

## Tech Stack

- Python 3
- FastAPI
- SQLite
- Pydantic
- Pytest
- Ollama Python client for LLM extraction

## Project Structure

```text
app/
  main.py                 FastAPI app setup and lifecycle
  config.py               Environment-driven settings
  db.py                   SQLite database layer
  schemas.py              Request and response models
  errors.py               Shared API error handling
  dependencies.py         FastAPI dependency wiring
  routers/
    notes.py              Note endpoints
    action_items.py       Action item endpoints
  services/
    extract.py            Heuristic and LLM extraction logic
frontend/
  index.html              Minimal browser UI
tests/
  test_api.py             API tests
  test_extract.py         Extraction unit tests
data/
  app.db                  Default SQLite database location
```

## Setup

The repository does not currently include a dependency manifest such as `requirements.txt` or `pyproject.toml`, so install the dependencies directly.

1. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install the required packages.

```bash
python -m pip install fastapi "uvicorn[standard]" pydantic python-dotenv pytest ollama
```

3. Optional: prepare Ollama if you want the dedicated LLM endpoint to work.

```bash
ollama pull mistral-nemo:12b
```

If Ollama is not installed or the model is unavailable:

- `POST /action-items/extract` can still succeed because it falls back to heuristic extraction by default
- `POST /action-items/extract-llm` returns `503 Service Unavailable`

## Configuration

Settings are loaded from environment variables in `app/config.py`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ACTION_ITEM_APP_NAME` | `Action Item Extractor` | FastAPI application title |
| `ACTION_ITEM_FRONTEND_DIR` | `frontend/` | Directory served for the frontend |
| `ACTION_ITEM_DATA_DIR` | `data/` | Data directory for runtime files |
| `ACTION_ITEM_DB_PATH` | `data/app.db` | SQLite database path |
| `OLLAMA_MODEL` | `mistral-nemo:12b` | Model used by the LLM extractor |
| `ACTION_ITEM_ALLOW_LLM_FALLBACK` | `true` | Enables fallback from LLM extraction to heuristics on the standard extract route |

Example:

```bash
export OLLAMA_MODEL=llama3.1
export ACTION_ITEM_DB_PATH=./data/dev.db
```

## Running the Project

From the project root, start the API server with Uvicorn:

```bash
uvicorn app.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/` for the frontend
- `http://127.0.0.1:8000/docs` for the interactive API docs

When the app starts, it:

- Creates the SQLite database directory if needed
- Initializes the `notes` and `action_items` tables
- Registers the configured action item extractor in app state

## Frontend

The frontend is a single static HTML page served at `/`. It lets you:

- Paste meeting notes or other free-form text
- Extract action items with the standard route
- Extract action items with the dedicated LLM route
- Save the input as a note
- Toggle action item completion
- List previously saved notes

## API Overview

### Notes

#### `POST /notes`

Create a note.

Request body:

```json
{
  "content": "Review the system design with the team"
}
```

Response:

```json
{
  "id": 1,
  "content": "Review the system design with the team",
  "created_at": "2026-03-20 08:00:00"
}
```

#### `GET /notes`

List all saved notes in descending ID order.

#### `GET /notes/{note_id}`

Retrieve a single note by ID.

### Action Items

#### `POST /action-items/extract`

Extract action items using the standard extractor. This route tries the LLM extractor first and falls back to heuristics if LLM extraction fails and fallback is enabled.

Request body:

```json
{
  "text": "todo: Write tests\n- Update README",
  "save_note": true
}
```

Response shape:

```json
{
  "note_id": 1,
  "extractor": "heuristic",
  "items": [
    {
      "id": 1,
      "note_id": 1,
      "text": "Write tests",
      "done": false,
      "created_at": "2026-03-20 08:00:00"
    }
  ]
}
```

Notes:

- If `save_note` is `true`, the note is stored and returned via `note_id`
- If `save_note` is `false`, action items are still stored, but with `note_id: null`
- The `extractor` field indicates which extraction path actually produced the result

#### `POST /action-items/extract-llm`

Extract action items using the dedicated Ollama-backed LLM flow. This route does not fall back to heuristics; it returns `503` if the LLM path is unavailable.

#### `GET /action-items`

List all action items.

Optional query parameter:

- `note_id`: return only action items associated with a specific note

Example:

```text
GET /action-items?note_id=1
```

#### `POST /action-items/{action_item_id}/done`

Mark an action item as done or not done.

Request body:

```json
{
  "done": true
}
```

## Error Responses

The API uses a shared JSON error shape from `app/errors.py`.

Common responses include:

- `400` for invalid input, with `error_code: "validation_error"`
- `404` for missing notes or action items, with `error_code: "not_found"`
- `503` when the extraction service is unavailable, with `error_code: "service_unavailable"`
- `500` for unexpected server errors, with `error_code: "internal_error"`

Example:

```json
{
  "detail": "text is required",
  "error_code": "validation_error",
  "errors": [
    {
      "type": "value_error",
      "loc": ["body", "text"],
      "msg": "Value error, text is required"
    }
  ]
}
```

## Running Tests

Run the full test suite from the project root:

```bash
python -m pytest -q
```

Current coverage includes:

- API behavior for notes and action item routes
- Validation and shared error response handling
- Heuristic extraction behavior
- LLM extraction parsing and fallback behavior

The test suite passed locally with:

```text
16 passed in 1.62s
```

## Notes for Development

- The database is stored at `data/app.db` by default
- The root route serves `frontend/index.html`
- FastAPI auto-generates API docs at `/docs`
- The code currently uses some Pydantic v1-style APIs, which raise deprecation warnings under Pydantic v2 during tests
