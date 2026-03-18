from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .db import Database
from .errors import NotFoundError, register_exception_handlers
from .routers import action_items, notes
from .services.extract import ActionItemExtractor


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(resolved_settings.database_path)
        database.initialize()
        app.state.settings = resolved_settings
        app.state.database = database
        app.state.action_item_extractor = ActionItemExtractor(
            model_name=resolved_settings.ollama_model,
            allow_fallback=resolved_settings.allow_llm_fallback,
        )
        yield

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(notes.router)
    app.include_router(action_items.router)
    app.mount(
        "/static",
        StaticFiles(directory=str(resolved_settings.frontend_dir)),
        name="static",
    )

    @app.get("/", include_in_schema=False)
    def index(request: Request) -> FileResponse:
        html_path = request.app.state.settings.frontend_dir / "index.html"
        if not html_path.exists():
            raise NotFoundError("frontend index.html was not found")
        return FileResponse(html_path)

    return app


app = create_app()
