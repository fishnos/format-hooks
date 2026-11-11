"""The `format-hooks` command; each rule module adds its subcommand via `register`."""

import argparse
import sys

from format_hooks import config_drift, density, pronouns, ruff_format, spacing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='format-hooks')
    subparsers = parser.add_subparsers(dest='command', required=True)
    spacing.register(subparsers)
    ruff_format.register(subparsers)
    config_drift.register(subparsers)
    pronouns.register(subparsers)
    density.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)

    return arguments.run(arguments)


if __name__ == '__main__':
    sys.exit(main())
