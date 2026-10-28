"""immo-buzz: high yield real estate opportunity tracker for Lille."""

__all__ = ["main"]


def main() -> None:
    """Console entry point exposed as ``immo-buzz``."""
    from immo_buzz.cli import main as cli_main

    cli_main()
