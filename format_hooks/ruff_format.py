"""Format, add trailing commas (COM812), format again.

COM812 only fires on a call already split across lines, so one pass leaves a
long call on one shared line. A call nested inside another needs a round per
level, so the comma-and-format step repeats until the files stop changing.
"""

import pathlib
import subprocess
import sys

_MAX_ROUNDS = 5


def _ruff(*arguments: str) -> None:
    subprocess.run([sys.executable, '-m', 'ruff', *arguments, '--quiet'], check=True)


def run(arguments) -> int:
    if not arguments.paths:
        return 0

    before = _read_all(arguments.paths)
    _ruff('format', '--force-exclude', *arguments.paths)

    for _ in range(_MAX_ROUNDS):
        round_start = _read_all(arguments.paths)
        _ruff(
            'check',
            '--fix',
            '--exit-zero',
            '--select',
            'COM812',
            '--force-exclude',
            *arguments.paths,
        )
        _ruff('format', '--force-exclude', *arguments.paths)

        if _read_all(arguments.paths) == round_start:
            break

    return 1 if _read_all(arguments.paths) != before else 0


def _read_all(paths) -> dict[str, bytes]:
    return {path: pathlib.Path(path).read_bytes() for path in paths}


def register(subparsers) -> None:
    parser = subparsers.add_parser('ruff-format', help='ruff format with one argument per line')
    parser.add_argument('paths', nargs='*')
    parser.set_defaults(run=run)
