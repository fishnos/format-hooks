"""Which files a rule looks at when run by hand.

Skipping is left to git: without paths, every file git knows about is checked,
untracked ones included, and anything gitignored is left out. A repository with
no commits yet still gets checked.
"""

import os
import subprocess


def select_files(paths: list[str], suffixes: tuple[str, ...], root: str) -> list[str]:
    if paths:
        return [path for path in paths if path.endswith(suffixes)]

    listed = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    return [os.path.join(root, name) for name in listed if name.endswith(suffixes)]
