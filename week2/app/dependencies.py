from __future__ import annotations

from fastapi import Request

from .config import Settings
from .db import Database
from .services.extract import ActionItemExtractor


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_action_item_extractor(request: Request) -> ActionItemExtractor:
    return request.app.state.action_item_extractor
