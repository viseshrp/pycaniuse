"""CLI entry point and orchestration for pycaniuse."""

from __future__ import annotations

import click
from rich.console import Console

from . import __version__ as _version
from .constants import PARSE_WARNING_LINE
from .exceptions import CaniuseError
from .http import fetch_feature_page, fetch_search_page
from .parse_feature import parse_feature_basic, parse_feature_full
from .parse_search import parse_search_results
from .render_basic import render_basic
from .ui.fullscreen import run_fullscreen
from .ui.select import select_match


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("query", nargs=-1, required=True)
@click.option("--full", "full_mode", is_flag=True, help="Enable full-screen interactive mode.")
@click.version_option(_version, "-v", "--version")
def main(query: tuple[str, ...], full_mode: bool) -> None:
    """Query caniuse.com from the terminal."""
    query_text = " ".join(query).strip()
    console = Console()

    try:
        search_html = fetch_search_page(query_text)
        matches = parse_search_results(search_html)

        if not matches:
            console.print(f"No matches found for query: {query_text}", style="yellow")
            raise click.exceptions.Exit(1)

        exact_match = next((item for item in matches if item.slug == query_text.lower()), None)
        slug: str | None
        if exact_match:
            slug = exact_match.slug
        elif len(matches) == 1:
            slug = matches[0].slug
        else:
            slug = select_match(matches)
            if slug is None:
                raise click.exceptions.Exit(1)
        if slug is None:  # pragma: no cover - defensive
            raise click.exceptions.Exit(1)

        feature_html = fetch_feature_page(slug)

        if full_mode:
            feature_full = parse_feature_full(feature_html, slug)
            if feature_full.parse_warnings:
                console.print(PARSE_WARNING_LINE, style="yellow")
            run_fullscreen(feature_full)
            return

        feature_basic = parse_feature_basic(feature_html, slug)
        if feature_basic.parse_warnings:
            console.print(PARSE_WARNING_LINE, style="yellow")
        console.print(render_basic(feature_basic))
    except CaniuseError as exc:
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":  # pragma: no cover
    main()
