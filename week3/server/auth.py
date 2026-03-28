from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status

from .config import Settings


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _auth_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": 'Bearer realm="spotify-mcp"'},
    )


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    audience: str
    issued_at: int
    expires_at: int


class LocalBearerTokenService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._secret = settings.mcp_auth_secret.encode("utf-8")

    def issue_token(
        self,
        *,
        subject: str,
        audience: str | None = None,
        expires_in_seconds: int | None = None,
    ) -> dict[str, Any]:
        now = int(time.time())
        ttl = expires_in_seconds or self._settings.mcp_token_ttl_seconds
        resolved_audience = audience or self._settings.mcp_token_audience
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": self._settings.public_base_url,
            "sub": subject,
            "aud": resolved_audience,
            "iat": now,
            "exp": now + ttl,
        }
        signing_input = ".".join(
            [
                _urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
                _urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
            ]
        )
        signature = hmac.new(
            self._secret,
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        token = f"{signing_input}.{_urlsafe_b64encode(signature)}"
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": ttl,
            "audience": resolved_audience,
        }

    def validate_token(self, token: str) -> TokenClaims:
        try:
            encoded_header, encoded_payload, encoded_signature = token.split(".")
        except ValueError as exc:
            raise _auth_error(
                "Invalid bearer token format. Visit /auth/login to obtain a fresh token."
            ) from exc

        signing_input = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            self._secret,
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        try:
            provided_signature = _urlsafe_b64decode(encoded_signature)
        except Exception as exc:  # pragma: no cover - defensive branch
            raise _auth_error(
                "Bearer token signature is unreadable. Visit /auth/login to obtain a fresh token."
            ) from exc

        if not hmac.compare_digest(expected_signature, provided_signature):
            raise _auth_error("Bearer token signature is invalid. Visit /auth/login for a new token.")

        try:
            payload = json.loads(_urlsafe_b64decode(encoded_payload))
        except Exception as exc:
            raise _auth_error(
                "Bearer token payload is invalid. Visit /auth/login to obtain a fresh token."
            ) from exc

        audience = payload.get("aud")
        if isinstance(audience, list):
            audiences = [str(item) for item in audience]
        elif audience is None:
            audiences = []
        else:
            audiences = [str(audience)]

        if self._settings.mcp_token_audience not in audiences:
            raise _auth_error(
                "Bearer token audience is invalid for this server. Visit /auth/login and request a token "
                f"for audience {self._settings.mcp_token_audience!r}."
            )

        now = int(time.time())
        expires_at = int(payload.get("exp", 0))
        if expires_at <= now:
            raise _auth_error("Bearer token expired. Visit /auth/login to obtain a fresh token.")

        subject = str(payload.get("sub") or "anonymous")
        issued_at = int(payload.get("iat", now))
        return TokenClaims(
            subject=subject,
            audience=self._settings.mcp_token_audience,
            issued_at=issued_at,
            expires_at=expires_at,
        )


async def require_bearer_token(request: Request) -> TokenClaims:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _auth_error("Authentication required. Visit /auth/login to obtain a bearer token.")
    token_service: LocalBearerTokenService = request.app.state.token_service
    return token_service.validate_token(token)
