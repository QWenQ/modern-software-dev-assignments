from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    detail: str
    error_code: str


class ValidationErrorResponse(ErrorResponse):
    errors: list[dict[str, Any]]


class AppError(Exception):
    def __init__(self, detail: str, *, status_code: int, error_code: str) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code


class NotFoundError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=404, error_code="not_found")


class ServiceError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=503, error_code="service_unavailable")


COMMON_ERROR_RESPONSES = {
    400: {"model": ValidationErrorResponse, "description": "Invalid request payload."},
    404: {"model": ErrorResponse, "description": "Requested resource was not found."},
    500: {"model": ErrorResponse, "description": "Unexpected server error."},
    503: {"model": ErrorResponse, "description": "A required dependency is unavailable."},
}


def _normalize_validation_message(message: str) -> str:
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message


def _make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        payload = ErrorResponse(detail=exc.detail, error_code=exc.error_code)
        return JSONResponse(status_code=exc.status_code, content=payload.dict())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [_make_json_safe(dict(error)) for error in exc.errors()]
        detail = "Invalid request payload."
        if errors:
            detail = _normalize_validation_message(str(errors[0].get("msg", detail)))
        payload = ValidationErrorResponse(
            detail=detail,
            error_code="validation_error",
            errors=errors,
        )
        return JSONResponse(status_code=400, content=payload.dict())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error", exc_info=exc)
        payload = ErrorResponse(detail="Internal server error", error_code="internal_error")
        return JSONResponse(status_code=500, content=payload.dict())
