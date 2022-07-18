"""Command-line interface."""
import click


@click.command()
@click.version_option()
def main() -> None:
    """Pycaniuse."""


if __name__ == "__main__":
    main(prog_name="pycaniuse")  # pragma: no cover
