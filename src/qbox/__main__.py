"""Command-line interface."""
import click


@click.command()
@click.version_option()
def main() -> None:
    """Quantum Box."""


if __name__ == "__main__":
    main(prog_name="qbox")  # pragma: no cover
