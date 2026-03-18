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
DEFAULT_FRONTEND_DIR = BASE_DIR / "frontend"
DEFAULT_DATA_DIR = BASE_DIR / "data"


if load_dotenv is not None:
    load_dotenv()


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    frontend_dir: Path
    data_dir: Path
    database_path: Path
    ollama_model: str
    allow_llm_fallback: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    frontend_dir = Path(os.getenv("ACTION_ITEM_FRONTEND_DIR", DEFAULT_FRONTEND_DIR))
    data_dir = Path(os.getenv("ACTION_ITEM_DATA_DIR", DEFAULT_DATA_DIR))
    database_path = Path(os.getenv("ACTION_ITEM_DB_PATH", data_dir / "app.db"))
    return Settings(
        app_name=os.getenv("ACTION_ITEM_APP_NAME", "Action Item Extractor"),
        frontend_dir=frontend_dir,
        data_dir=data_dir,
        database_path=database_path,
        ollama_model=os.getenv("OLLAMA_MODEL", "mistral-nemo:12b"),
        allow_llm_fallback=_get_bool_env("ACTION_ITEM_ALLOW_LLM_FALLBACK", True),
    )
