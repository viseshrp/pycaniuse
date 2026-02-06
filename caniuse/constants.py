"""Constants used across pycaniuse."""

from __future__ import annotations

from typing import Final

BASE_URL: Final[str] = "https://caniuse.com"
SEARCH_URL: Final[str] = f"{BASE_URL}/"
FEATURE_URL_TEMPLATE: Final[str] = f"{BASE_URL}/{{slug}}"

BASIC_MODE_BROWSERS: Final[tuple[str, ...]] = (
    "chrome",
    "edge",
    "firefox",
    "safari",
    "opera",
)

STATUS_ICON_MAP: Final[dict[str, str]] = {
    "y": "✅",
    "n": "❌",
    "a": "◐",
    "u": "﹖",
}

STATUS_LABEL_MAP: Final[dict[str, str]] = {
    "y": "Supported",
    "n": "Not supported",
    "a": "Partial support",
    "u": "Unknown",
}

PARSE_WARNING_LINE: Final[str] = "Some sections could not be parsed (site layout may have changed)."
FULL_MODE_HINT: Final[str] = "Run with --full to see all browsers + Notes/Resources/Sub-features."

DEFAULT_TIMEOUT_SECONDS: Final[float] = 10.0
