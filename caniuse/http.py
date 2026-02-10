"""HTTP client layer for pycaniuse."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
import json
from typing import Any

import httpx

from ._version import __version__
from .constants import (
    DEFAULT_TIMEOUT_SECONDS,
    FEATURE_DATA_URL,
    FEATURE_URL_TEMPLATE,
    SEARCH_QUERY_URL,
    SEARCH_URL,
)
from .exceptions import ContentError, HttpStatusError, NetworkError, RequestTimeoutError

_SHARED_CLIENT: ContextVar[httpx.Client | None] = ContextVar(
    "pycaniuse_shared_client", default=None
)


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent": f"pycaniuse/{__version__}",
        "Accept": "text/html,application/xhtml+xml",
    }


@contextmanager
def use_shared_client(
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Iterator[httpx.Client]:
    """Provide a reusable HTTP client for all fetches within a CLI run."""
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=_build_headers()) as client:
        token = _SHARED_CLIENT.set(client)
        try:
            yield client
        finally:
            _SHARED_CLIENT.reset(token)


def fetch_html(
    url: str,
    params: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    *,
    allow_static_fallback: bool = False,
) -> str:
    """Fetch an HTML document with deterministic behavior and friendly failures."""
    request_params = dict(params or {})
    shared_client = _SHARED_CLIENT.get()

    def _request(current_params: dict[str, str]) -> str:
        retry_once = True
        while True:
            try:
                if shared_client is None or timeout != DEFAULT_TIMEOUT_SECONDS:
                    with httpx.Client(
                        timeout=timeout, follow_redirects=True, headers=_build_headers()
                    ) as client:
                        response = client.get(url, params=current_params)
                else:
                    response = shared_client.get(url, params=current_params)
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


def _post_form(
    url: str,
    form_data: Mapping[str, str],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Submit URL-encoded form data and return response text."""
    shared_client = _SHARED_CLIENT.get()
    payload = dict(form_data)
    retry_once = True
    while True:
        try:
            if shared_client is None or timeout != DEFAULT_TIMEOUT_SECONDS:
                with httpx.Client(
                    timeout=timeout, follow_redirects=True, headers=_build_headers()
                ) as client:
                    response = client.post(url, data=payload)
            else:
                response = shared_client.post(url, data=payload)
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


def _parse_json_payload(raw: str, url: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContentError(url) from exc


def _normalize_feature_ids(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        feature_id = value.strip().lower()
        if not feature_id or feature_id in seen:
            continue
        seen.add(feature_id)
        output.append(feature_id)
    return output


def fetch_search_feature_ids(query: str) -> list[str]:
    """Fetch ordered feature IDs from caniuse search backend."""
    payload = _parse_json_payload(
        fetch_html(SEARCH_QUERY_URL, params={"search": query}),
        SEARCH_QUERY_URL,
    )
    if not isinstance(payload, dict):
        raise ContentError(SEARCH_QUERY_URL)

    raw_ids = payload.get("featureIds") or payload.get("feature_ids") or []
    if not isinstance(raw_ids, list):
        return []

    return _normalize_feature_ids([item for item in raw_ids if isinstance(item, str)])


def fetch_support_data(
    *,
    full_data_feats: Sequence[str] | None = None,
    meta_data_feats: Sequence[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch support-data payload from caniuse backend."""
    full_ids = _normalize_feature_ids(full_data_feats)
    meta_ids = _normalize_feature_ids(meta_data_feats)
    if not full_ids and not meta_ids:
        return {}

    form_data: dict[str, str] = {"type": "support-data"}
    if full_ids:
        form_data["fullDataFeats"] = ",".join(full_ids)
    if meta_ids:
        form_data["metaDataFeats"] = ",".join(meta_ids)

    raw_payload = _post_form(FEATURE_DATA_URL, form_data, timeout=timeout)
    payload = _parse_json_payload(raw_payload, FEATURE_DATA_URL)
    if not isinstance(payload, dict):
        raise ContentError(FEATURE_DATA_URL)
    return payload


def fetch_feature_aux_data(slug: str, data_type: str) -> list[dict[str, Any]]:
    """Fetch per-feature auxiliary list data (e.g. bugs, links)."""
    payload = _parse_json_payload(
        fetch_html(FEATURE_DATA_URL, params={"feat": slug, "type": data_type}),
        FEATURE_DATA_URL,
    )
    if not isinstance(payload, list):
        raise ContentError(FEATURE_DATA_URL)
    return [entry for entry in payload if isinstance(entry, dict)]


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
