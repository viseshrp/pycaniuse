"""HTML parsing helpers built around justhtml."""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urljoin

from justhtml import JustHTML

from .text import normalize_whitespace

Node = Any
LOGGER = logging.getLogger(__name__)


def parse_document(html: str) -> JustHTML:
    """Parse HTML without sanitization to preserve all structural tags."""
    return JustHTML(html, sanitize=False, safe=False)


def first(node: Node, selector: str) -> Node | None:
    """Return the first selector match or None."""
    matches = all_nodes(node, selector)
    return matches[0] if matches else None


def all_nodes(node: Node, selector: str) -> list[Node]:
    """Return all selector matches, guarding selector/runtime errors."""
    try:
        if hasattr(node, "query"):
            return list(node.query(selector))
    except Exception:
        return []
    return []


def text(node: Node | None) -> str:
    """Extract normalized text from a node."""
    if node is None:
        return ""
    try:
        if hasattr(node, "to_text"):
            return normalize_whitespace(node.to_text())
        if hasattr(node, "data") and isinstance(node.data, str):
            return normalize_whitespace(node.data)
    except Exception:
        return ""
    return ""


def markdown_text(node: Node | None) -> str:
    """Extract markdown-like text from a node when available."""
    if node is None:
        return ""
    try:
        if hasattr(node, "to_markdown"):
            return normalize_whitespace(node.to_markdown())
    except Exception:
        return text(node)
    return text(node)


def attr(node: Node | None, name: str) -> str | None:
    """Get an element attribute by name."""
    if node is None:
        return None
    attrs = getattr(node, "attrs", None)
    if not isinstance(attrs, dict):
        return None
    value = attrs.get(name)
    if value is None:
        return None
    return str(value)


def class_tokens(node: Node | None) -> tuple[str, ...]:
    """Return element classes as tokenized tuple."""
    class_attr = attr(node, "class")
    if not class_attr:
        return ()
    return tuple(token for token in class_attr.split() if token)


def safe_join_url(base: str, href: str | None) -> str | None:
    """Join relative URLs against a base URL."""
    if not href:
        return None
    return urljoin(base, href)


def debug_enabled() -> bool:
    """Check debug mode env flag."""
    return os.environ.get("PYCANIUSE_DEBUG", "").strip() == "1"


def debug_log(message: str) -> None:
    """Emit debug logs to stderr in debug mode only."""
    if debug_enabled():
        LOGGER.debug("%s", message)
