"""Exception types for pycaniuse."""

from __future__ import annotations


class CaniuseError(Exception):
    """Base exception for expected application errors."""


class NetworkError(CaniuseError):
    """Raised when a network operation fails."""

    def __init__(self, url: str, *, cause: str | None = None) -> None:
        detail = f"Unable to connect to caniuse.com for {url}"
        if cause:
            detail = f"{detail} ({cause})"
        super().__init__(detail)


class RequestTimeoutError(CaniuseError):
    """Raised when a request times out."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Request timed out for {url}")


class HttpStatusError(CaniuseError):
    """Raised when a non-200 HTTP response is returned."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"Request failed with HTTP {status_code} for {url}")


class ContentError(CaniuseError):
    """Raised when a response body is invalid or unexpectedly empty."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Received empty HTML content from {url}")
