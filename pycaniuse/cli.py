"""Console script for pycaniuse."""

import click
from click_default_group import DefaultGroup

from . import __version__

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(
    cls=DefaultGroup,
    context_settings=CONTEXT_SETTINGS,
)
@click.version_option(__version__, "-v", "--version")
def main():
    """

    """
    pass


@main.command(default=True)
@click.argument(
    "feature",
    metavar="<feature>",
    nargs=-1,
    required=False,
    type=click.STRING,
)
def caniuse(feature):
    """
    """
    pass


if __name__ == "__main__":
    main()
