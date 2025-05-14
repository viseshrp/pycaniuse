"""Console script for caniuse."""

import click

from . import __version__ as _version
from .caniuse import do_stuff


@click.argument(
    "stuff",
    metavar="<what_you_worked_on>",
    nargs=-1,
    required=False,
    type=click.STRING,
)
@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(_version, "-v", "--version")
def main(stuff: str) -> None:
    """
    Query caniuse.com from the terminal

    \b
    Example usages:

    """
    do_stuff(stuff)
