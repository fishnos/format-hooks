import subprocess
import sys

SOURCE_MISSING_BLANK_BEFORE_RETURN = (
    'def doubled(value):\n    result = value * 2\n    return result\n'
)


def _run_spacing(*arguments):
    return subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'python-spacing', *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_fails_and_names_a_file_missing_the_blank_line_before_return(tmp_path):
    source_path = tmp_path / 'module.py'
    source_path.write_text(SOURCE_MISSING_BLANK_BEFORE_RETURN)

    result = _run_spacing('--check', str(source_path))

    assert result.returncode == 1
    assert f'{source_path}:3: blank line needed before return' in result.stdout


def test_check_writes_nothing(tmp_path):
    source_path = tmp_path / 'module.py'
    source_path.write_text(SOURCE_MISSING_BLANK_BEFORE_RETURN)

    _run_spacing('--check', str(source_path))

    assert source_path.read_text() == SOURCE_MISSING_BLANK_BEFORE_RETURN


def test_check_passes_once_the_file_is_formatted(tmp_path):
    source_path = tmp_path / 'module.py'
    source_path.write_text(SOURCE_MISSING_BLANK_BEFORE_RETURN)
    _run_spacing(str(source_path))

    result = _run_spacing('--check', str(source_path))

    assert result.returncode == 0


def test_formatting_names_the_rewritten_file(tmp_path):
    source_path = tmp_path / 'module.py'
    source_path.write_text(SOURCE_MISSING_BLANK_BEFORE_RETURN)

    result = _run_spacing(str(source_path))

    assert result.stdout == f'formatted {source_path}\n'


def test_formatting_keeps_crlf_line_endings_on_disk(tmp_path):
    source_path = tmp_path / 'module.py'
    source_path.write_bytes(b'def f(x):\r\n    y = x\r\n    return y\r\n')

    _run_spacing(str(source_path))

    assert source_path.read_bytes() == b'def f(x):\r\n    y = x\r\n\r\n    return y\r\n'


def test_file_that_is_not_utf8_is_skipped_and_left_byte_identical(tmp_path):
    source_path = tmp_path / 'legacy.py'
    source_bytes = b'def f():\n    x = "\xe9"\n    return x\n'
    source_path.write_bytes(source_bytes)

    result = _run_spacing(str(source_path))

    assert result.returncode == 0
    assert source_path.read_bytes() == source_bytes
