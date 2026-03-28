from __future__ import annotations


class SpotifyAPIError(Exception):
    """Base exception for Spotify API errors."""


class SpotifyAuthError(SpotifyAPIError):
    """Raised when Spotify client-credential auth fails."""


class SpotifyRateLimitError(SpotifyAPIError):
    """Raised when Spotify returns HTTP 429."""
