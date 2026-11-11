"""The `sync-config` hook, run through pre-commit itself against this checkout."""

import pathlib
import shutil
import subprocess

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parent.parent
SHARED_FILE_NAMES = ('ruff.toml', '.clang-format', '.prettierrc.json', '.editorconfig')

pytestmark = pytest.mark.skipif(shutil.which('pre-commit') is None, reason='needs pre-commit')


def _run_hook(target: pathlib.Path, *stage_arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['pre-commit', 'try-repo', str(REPOSITORY_ROOT), 'sync-config', *stage_arguments],
        cwd=target,
        capture_output=True,
        text=True,
    )


def _empty_git_repository(tmp_path: pathlib.Path) -> pathlib.Path:
    subprocess.run(['git', 'init', '--quiet', str(tmp_path)], check=True)

    return tmp_path


def test_manual_sync_config_hook_writes_the_four_shared_files(tmp_path):
    target = _empty_git_repository(tmp_path)

    _run_hook(target, '--hook-stage', 'manual')

    assert sorted(path.name for path in target.iterdir() if path.name != '.git') == sorted(
        SHARED_FILE_NAMES,
    )


def test_sync_config_hook_does_not_run_on_commit(tmp_path):
    target = _empty_git_repository(tmp_path)

    _run_hook(target)

    assert [path.name for path in target.iterdir() if path.name != '.git'] == []
