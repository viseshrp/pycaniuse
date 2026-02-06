"""HTTP client layer for pycaniuse."""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from ._version import __version__
from .constants import DEFAULT_TIMEOUT_SECONDS, FEATURE_URL_TEMPLATE, SEARCH_URL
from .exceptions import ContentError, HttpStatusError, NetworkError, RequestTimeoutError


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent": f"pycaniuse/{__version__}",
        "Accept": "text/html,application/xhtml+xml",
    }


def fetch_html(
    url: str,
    params: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    *,
    allow_static_fallback: bool = False,
) -> str:
    """Fetch an HTML document with deterministic behavior and friendly failures."""
    request_params = dict(params or {})

    def _request(current_params: dict[str, str]) -> str:
        retry_once = True
        while True:
            try:
                with httpx.Client(
                    timeout=timeout, follow_redirects=True, headers=_build_headers()
                ) as client:
                    response = client.get(url, params=current_params)
            except httpx.TimeoutException as exc:
                raise RequestTimeoutError(url) from exc
            except httpx.ConnectError as exc:
                if retry_once:
                    retry_once = False
                    continue
                raise NetworkError(url, cause=exc.__class__.__name__) from exc
            except httpx.RequestError as exc:
                raise NetworkError(url, cause=exc.__class__.__name__) from exc

            if response.status_code != 200:
                raise HttpStatusError(response.status_code, str(response.url))

            body = response.text
            if not body.strip():
                raise ContentError(str(response.url))
            return body

    try:
        return _request(request_params)
    except HttpStatusError:
        if allow_static_fallback and request_params.get("static") == "1":
            fallback_params = dict(request_params)
            fallback_params.pop("static", None)
            return _request(fallback_params)
        raise


def fetch_search_page(query: str) -> str:
    """Fetch the caniuse search results page for query."""
    return fetch_html(SEARCH_URL, params={"search": query, "static": "1"})


def fetch_feature_page(slug: str) -> str:
    """Fetch a caniuse feature page, with static fallback."""
    return fetch_html(
        FEATURE_URL_TEMPLATE.format(slug=slug),
        params={"static": "1"},
        allow_static_fallback=True,
    )
