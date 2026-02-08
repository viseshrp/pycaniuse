from __future__ import annotations

from typing import ClassVar

import httpx
import pytest

from caniuse import caniuse as caniuse_shim
from caniuse import http
from caniuse.constants import FEATURE_URL_TEMPLATE, SEARCH_URL
from caniuse.exceptions import ContentError, HttpStatusError, NetworkError, RequestTimeoutError


class _FakeClient:
    plans: ClassVar[list[object]] = []
    seen_params: ClassVar[list[dict[str, str] | None]] = []

    def __init__(self, **_: object) -> None:
        pass

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object | None,
    ) -> None:
        return None

    def get(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        _FakeClient.seen_params.append(params)
        plan = _FakeClient.plans.pop(0)
        if isinstance(plan, Exception):
            raise plan
        if isinstance(plan, tuple):
            status_code, text = plan
            return httpx.Response(
                status_code,
                text=text,
                request=httpx.Request("GET", url, params=params),
            )
        raise AssertionError


def _reset_plans(*plans: object) -> None:
    _FakeClient.plans = list(plans)
    _FakeClient.seen_params = []


def test_caniuse_shim_exports_main() -> None:
    assert callable(caniuse_shim.main)


def test_exception_messages() -> None:
    assert "Unable to connect" in str(NetworkError("https://caniuse.com/x"))
    assert "Boom" in str(NetworkError("https://caniuse.com/x", cause="Boom"))
    assert "timed out" in str(RequestTimeoutError("https://caniuse.com/x"))
    assert "HTTP 503" in str(HttpStatusError(503, "https://caniuse.com/x"))
    assert "empty HTML" in str(ContentError("https://caniuse.com/x"))


def test_fetch_html_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_plans((200, "<html>ok</html>"))
    monkeypatch.setattr(http.httpx, "Client", _FakeClient)

    result = http.fetch_html("https://caniuse.com/flexbox", params={"a": "1"})

    assert result == "<html>ok</html>"
    assert _FakeClient.seen_params[-1] == {"a": "1"}


def test_fetch_html_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    timeout_exc = httpx.TimeoutException("slow")
    _reset_plans(timeout_exc)
    monkeypatch.setattr(http.httpx, "Client", _FakeClient)

    with pytest.raises(RequestTimeoutError):
        http.fetch_html("https://caniuse.com/flexbox")


def test_fetch_html_connect_retry_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    connect_exc = httpx.ConnectError("conn", request=httpx.Request("GET", "https://caniuse.com"))
    _reset_plans(connect_exc, (200, "<html>retried</html>"))
    monkeypatch.setattr(http.httpx, "Client", _FakeClient)

    result = http.fetch_html("https://caniuse.com/flexbox")

    assert result == "<html>retried</html>"
    assert len(_FakeClient.seen_params) == 2


def test_fetch_html_connect_retry_then_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    connect_exc = httpx.ConnectError("conn", request=httpx.Request("GET", "https://caniuse.com"))
    _reset_plans(connect_exc, connect_exc)
    monkeypatch.setattr(http.httpx, "Client", _FakeClient)

    with pytest.raises(NetworkError):
        http.fetch_html("https://caniuse.com/flexbox")


def test_fetch_html_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    req_exc = httpx.RequestError("bad", request=httpx.Request("GET", "https://caniuse.com"))
    _reset_plans(req_exc)
    monkeypatch.setattr(http.httpx, "Client", _FakeClient)

    with pytest.raises(NetworkError):
        http.fetch_html("https://caniuse.com/flexbox")


def test_fetch_html_non_200_without_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_plans((500, "error"))
    monkeypatch.setattr(http.httpx, "Client", _FakeClient)

    with pytest.raises(HttpStatusError):
        http.fetch_html("https://caniuse.com/flexbox")


def test_fetch_html_fallback_without_static(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_plans((404, "notfound"), (200, "<html>fallback</html>"))
    monkeypatch.setattr(http.httpx, "Client", _FakeClient)

    result = http.fetch_html(
        "https://caniuse.com/flexbox",
        params={"static": "1", "search": "flexbox"},
        allow_static_fallback=True,
    )

    assert result == "<html>fallback</html>"
    assert _FakeClient.seen_params[0] == {"static": "1", "search": "flexbox"}
    assert _FakeClient.seen_params[1] == {"search": "flexbox"}


def test_fetch_html_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_plans((200, "   "))
    monkeypatch.setattr(http.httpx, "Client", _FakeClient)

    with pytest.raises(ContentError):
        http.fetch_html("https://caniuse.com/flexbox")


def test_fetch_search_and_feature_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, str] | None, bool]] = []

    def _fake_fetch_html(
        url: str,
        params: dict[str, str] | None = None,
        timeout: float = 10.0,
        *,
        allow_static_fallback: bool = False,
    ) -> str:
        _ = timeout
        calls.append((url, params, allow_static_fallback))
        return "<html></html>"

    monkeypatch.setattr(http, "fetch_html", _fake_fetch_html)

    assert http.fetch_search_page("grid") == "<html></html>"
    assert http.fetch_feature_page("flexbox") == "<html></html>"

    assert calls[0] == (SEARCH_URL, {"search": "grid", "static": "1"}, False)
    assert calls[1] == (
        FEATURE_URL_TEMPLATE.format(slug="flexbox"),
        {"static": "1"},
        True,
    )
