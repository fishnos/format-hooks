"""Which files a rule checks when run by hand.

Without paths, git decides: every file it knows about, untracked ones included,
gitignored ones left out, even in a repository with no commits yet.
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
