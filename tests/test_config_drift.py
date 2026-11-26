import importlib.resources
import subprocess
import sys

from format_hooks.config_drift import find_drift, sync_config

SHARED_RUFF_TEXT = """line-length = 100
target-version = "py312"

[lint]
select = ["E", "F", "W", "I", "B", "UP", "COM812"]

[format]
quote-style = "single"
"""


def copy_shared_files(repo_root):
    shared_folder = importlib.resources.files('format_hooks') / 'shared_config'

    for name in ('ruff.toml', '.clang-format', '.prettierrc.json', '.editorconfig'):
        (repo_root / name).write_bytes((shared_folder / name).read_bytes())


def test_shared_copies_are_not_drift(tmp_path):
    copy_shared_files(tmp_path)

    assert find_drift(str(tmp_path)) == []


def test_changed_shared_ruff_key_is_drift(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 120\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n',
    )

    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        'ruff.toml: line-length differs from format-hooks',
    ]


def test_changed_rule_selection_names_the_table_and_key(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n',
    )

    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        'ruff.toml: lint.select differs from format-hooks',
    ]


def test_absent_shared_ruff_key_is_drift(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n',
    )

    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        'ruff.toml: format.quote-style differs from format-hooks',
    ]


def test_repository_ignore_list_is_not_drift(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 100\n'
        'target-version = "py312"\n'
        'extend-exclude = ["third_party"]\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        'ignore = ["E501"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n',
    )

    assert find_drift(str(tmp_path)) == []


def test_missing_ruff_file_is_reported_once(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').unlink()

    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        'ruff.toml: missing; run: pre-commit run sync-config --hook-stage manual',
    ]


def test_unparseable_ruff_file_is_reported_once(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').write_text('line-length = \n')

    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        'ruff.toml: not valid TOML; fix it by hand, then run: '
        'pre-commit run sync-config --hook-stage manual',
    ]


def test_edited_clang_format_is_drift(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / '.clang-format').write_text('BasedOnStyle: Google\nColumnLimit: 120\n')

    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        '.clang-format: differs from format-hooks',
    ]


def test_every_missing_file_is_named_in_an_empty_repository(tmp_path):
    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        'ruff.toml: missing; run: pre-commit run sync-config --hook-stage manual',
        '.clang-format: missing; run: pre-commit run sync-config --hook-stage manual',
        '.prettierrc.json: missing; run: pre-commit run sync-config --hook-stage manual',
        '.editorconfig: missing; run: pre-commit run sync-config --hook-stage manual',
    ]


def test_sync_keeps_the_repository_ignore_list_and_its_comments(tmp_path):
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 120\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        'ignore = [\n'
        '    "E501",  # why\n'
        ']\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n',
    )

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == (
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        'ignore = [\n'
        '    "E501",  # why\n'
        ']\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n'
    )


def test_sync_replaces_a_multiline_rule_selection_and_keeps_its_trailing_comment(tmp_path):
    (tmp_path / 'ruff.toml').write_text(
        '# Repository ruff settings.\n'
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = [\n'
        '    "E",  # errors, with a ] inside the comment\n'
        '    "F",\n'
        ']  # picked by hand\n'
        'ignore = ["E501"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n',
    )

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == (
        '# Repository ruff settings.\n'
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]  # picked by hand\n'
        'ignore = ["E501"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n'
    )


def test_sync_leaves_an_equal_value_written_differently_alone(tmp_path):
    source = (
        'line-length = 100\n'
        "target-version = 'py312'\n"
        '\n'
        '[lint]\n'
        'select = [\n'
        '    "E", "F", "W", "I",\n'
        '    "B", "UP", "COM812",\n'
        ']\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n'
    )
    (tmp_path / 'ruff.toml').write_text(source)

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == source


def test_sync_inserts_a_missing_key_after_the_last_setting_of_its_table(tmp_path):
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'ignore = [\n'
        '    "E501",\n'
        ']\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n',
    )

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == (
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'ignore = [\n'
        '    "E501",\n'
        ']\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n'
    )


def test_sync_inserts_a_missing_top_level_key_after_the_other_top_level_settings(tmp_path):
    (tmp_path / 'ruff.toml').write_text(
        '# Repository ruff settings.\n'
        'line-length = 100\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n',
    )

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == (
        '# Repository ruff settings.\n'
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n'
    )


def test_sync_appends_a_missing_table_at_the_end(tmp_path):
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]',
    )

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == (
        'line-length = 100\n'
        'target-version = "py312"\n'
        '\n'
        '[lint]\n'
        'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        '\n'
        '[format]\n'
        'quote-style = "single"\n'
    )


def test_sync_replaces_a_dotted_top_level_key_instead_of_adding_a_table(tmp_path):
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 100\n'
        'target-version = "py312"\n'
        'lint.select = ["E"]\n'
        'format.quote-style = "single"\n',
    )

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == (
        'line-length = 100\n'
        'target-version = "py312"\n'
        'lint.select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
        'format.quote-style = "single"\n'
    )


def test_sync_keeps_crlf_line_endings(tmp_path):
    (tmp_path / 'ruff.toml').write_bytes(
        b'line-length = 120\r\n'
        b'target-version = "py312"\r\n'
        b'\r\n'
        b'[lint]\r\n'
        b'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\r\n',
    )

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_bytes() == (
        b'line-length = 100\r\n'
        b'target-version = "py312"\r\n'
        b'\r\n'
        b'[lint]\r\n'
        b'select = ["E", "F", "W", "I", "B", "UP", "COM812"]\r\n'
        b'\r\n'
        b'[format]\r\n'
        b'quote-style = "single"\r\n'
    )


def test_sync_copies_the_shared_ruff_file_when_the_repository_has_none(tmp_path):
    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == SHARED_RUFF_TEXT


def test_sync_overwrites_an_edited_editorconfig(tmp_path):
    (tmp_path / '.editorconfig').write_text('root = true\n')

    sync_config(str(tmp_path))

    assert (tmp_path / '.editorconfig').read_text() == (
        'root = true\n'
        '\n'
        '[*.{sh,bash}]\n'
        'indent_style = space\n'
        'indent_size = 2\n'
        'switch_case_indent = true\n'
    )


def test_sync_leaves_an_unparseable_ruff_file_alone(tmp_path):
    (tmp_path / 'ruff.toml').write_text('line-length = \n')

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == 'line-length = \n'


def test_sync_returns_every_file_it_wrote_in_an_empty_repository(tmp_path):
    assert sync_config(str(tmp_path)) == [
        'ruff.toml',
        '.clang-format',
        '.prettierrc.json',
        '.editorconfig',
    ]


def test_sync_returns_nothing_when_the_copies_already_match(tmp_path):
    copy_shared_files(tmp_path)

    assert sync_config(str(tmp_path)) == []


def test_drift_passes_after_sync(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 120\n\n[lint]\nselect = ["E"]\nignore = ["E501"]\n',
    )
    (tmp_path / '.clang-format').write_text('BasedOnStyle: LLVM\n')
    (tmp_path / '.prettierrc.json').unlink()

    sync_config(str(tmp_path))

    assert find_drift(str(tmp_path)) == []


def test_sync_adds_a_dotted_key_when_the_table_exists_only_as_dotted_keys(tmp_path):
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 100\n'
        'target-version = "py312"\n'
        'lint.ignore = ["E501"]\n'
        'format.quote-style = "single"\n',
    )

    sync_config(str(tmp_path))

    assert (tmp_path / 'ruff.toml').read_text() == (
        'line-length = 100\n'
        'target-version = "py312"\n'
        'lint.ignore = ["E501"]\n'
        'format.quote-style = "single"\n'
        'lint.select = ["E", "F", "W", "I", "B", "UP", "COM812"]\n'
    )


def test_config_drift_command_fails_and_names_the_missing_file(tmp_path):
    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'config-drift'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        'ruff.toml: missing; run: pre-commit run sync-config --hook-stage manual' in result.stdout
    )


def test_config_drift_command_passes_on_shared_copies(tmp_path):
    copy_shared_files(tmp_path)

    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'config-drift'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_sync_config_command_writes_the_copies_and_names_them(tmp_path):
    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'sync-config'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert 'synced .editorconfig' in result.stdout
    assert (tmp_path / '.editorconfig').exists()


def test_ruff_settings_in_pyproject_are_reported_instead_of_a_missing_ruff_file(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').unlink()
    (tmp_path / 'pyproject.toml').write_text('[tool.ruff]\nline-length = 120\n')

    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        'pyproject.toml: ruff settings live here; move them to ruff.toml',
    ]


def test_ruff_settings_in_dot_ruff_toml_are_reported(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'ruff.toml').unlink()
    (tmp_path / '.ruff.toml').write_text('line-length = 120\n')

    problems = find_drift(str(tmp_path))

    assert [problem.render() for problem in problems] == [
        '.ruff.toml: ruff settings live here; move them to ruff.toml',
    ]


def test_pyproject_without_ruff_settings_is_not_reported(tmp_path):
    copy_shared_files(tmp_path)
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "x"\n')

    assert find_drift(str(tmp_path)) == []


def test_sync_does_not_create_ruff_toml_beside_ruff_settings_in_pyproject(tmp_path):
    (tmp_path / 'pyproject.toml').write_text('[tool.ruff]\nline-length = 120\n')

    sync_config(str(tmp_path))

    assert not (tmp_path / 'ruff.toml').exists()


def test_sync_config_command_fails_and_names_the_file_holding_ruff_settings(tmp_path):
    (tmp_path / 'pyproject.toml').write_text('[tool.ruff]\nline-length = 120\n')

    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'sync-config'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert 'pyproject.toml: ruff settings live here; move them to ruff.toml' in result.stdout


def test_shared_settings_files_keep_unix_line_endings_in_a_windows_checkout():
    shared_folder = importlib.resources.files('format_hooks') / 'shared_config'

    assert b'\r' not in (shared_folder / 'ruff.toml').read_bytes()
    assert b'\r' not in (shared_folder / '.clang-format').read_bytes()
    assert b'\r' not in (shared_folder / '.prettierrc.json').read_bytes()
    assert b'\r' not in (shared_folder / '.editorconfig').read_bytes()
