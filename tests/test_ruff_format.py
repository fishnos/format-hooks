import subprocess
import sys

RUFF_SETTINGS = (
    'line-length = 100\n\n[format]\nquote-style = "single"\n\n[lint]\nselect = ["COM812"]\n'
)

TOO_LONG_CALL = (
    'result = compute_the_answer('
    'first_argument_value, second_argument_value, third_argument_value, fourth_value)\n'
)


def _run_ruff_format(*arguments, cwd):
    return subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'ruff-format', *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_one_run_puts_each_argument_of_a_wrapped_call_on_its_own_line(tmp_path):
    (tmp_path / 'ruff.toml').write_text(RUFF_SETTINGS)
    source_path = tmp_path / 'module.py'
    source_path.write_text(TOO_LONG_CALL)

    _run_ruff_format(str(source_path), cwd=tmp_path)

    assert source_path.read_text() == (
        'result = compute_the_answer(\n'
        '    first_argument_value,\n'
        '    second_argument_value,\n'
        '    third_argument_value,\n'
        '    fourth_value,\n'
        ')\n'
    )


def test_a_file_that_changed_fails_the_run(tmp_path):
    (tmp_path / 'ruff.toml').write_text(RUFF_SETTINGS)
    source_path = tmp_path / 'module.py'
    source_path.write_text(TOO_LONG_CALL)

    result = _run_ruff_format(str(source_path), cwd=tmp_path)

    assert result.returncode == 1


def test_an_already_formatted_file_passes_and_is_left_alone(tmp_path):
    (tmp_path / 'ruff.toml').write_text(RUFF_SETTINGS)
    source_path = tmp_path / 'module.py'
    source_path.write_text('value = 1\n')

    result = _run_ruff_format(str(source_path), cwd=tmp_path)

    assert result.returncode == 0
    assert source_path.read_text() == 'value = 1\n'


def test_other_lint_rules_are_not_applied(tmp_path):
    (tmp_path / 'ruff.toml').write_text(RUFF_SETTINGS.replace('"COM812"', '"COM812", "F401"'))
    source_path = tmp_path / 'module.py'
    source_path.write_text('import os\n')

    _run_ruff_format(str(source_path), cwd=tmp_path)

    assert source_path.read_text() == 'import os\n'


def test_one_run_settles_a_call_nested_inside_another_wrapped_call(tmp_path):
    (tmp_path / 'ruff.toml').write_text(RUFF_SETTINGS)
    source_path = tmp_path / 'module.py'
    source_path.write_text(
        'class Node:\n'
        '    def setup(self):\n'
        '        self.linear_noise_std = float(self.declare_parameter('
        "'linear_noise_std_m', SensorNoiseParams.LINEAR_NOISE_STD_M).value)\n",
    )
    _run_ruff_format(str(source_path), cwd=tmp_path)

    second_run = _run_ruff_format(str(source_path), cwd=tmp_path)

    assert second_run.returncode == 0
