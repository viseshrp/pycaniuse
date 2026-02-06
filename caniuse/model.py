"""Data models for search and feature parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class SearchMatch:
    slug: str
    title: str
    href: str


@dataclass(frozen=True)
class SupportRange:
    range_text: str
    status: Literal["y", "n", "a", "u"]
    is_past: bool
    is_current: bool
    is_future: bool
    title_attr: str
    raw_classes: tuple[str, ...]


@dataclass(frozen=True)
class BrowserSupportBlock:
    browser_name: str
    browser_key: str
    ranges: list[SupportRange]


@dataclass(frozen=True)
class FeatureBasic:
    slug: str
    title: str
    spec_url: str | None
    spec_status: str | None
    usage_supported: float | None
    usage_partial: float | None
    usage_total: float | None
    description_text: str
    browser_blocks: list[BrowserSupportBlock]
    parse_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FeatureFull(FeatureBasic):
    notes_text: str | None = None
    resources: list[tuple[str, str]] = field(default_factory=list)
    subfeatures: list[tuple[str, str]] = field(default_factory=list)
    tabs: dict[str, str] = field(default_factory=dict)
