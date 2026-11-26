import subprocess
import sys

from format_hooks.density import measure_comment_share

# 25 non-blank lines, 6 of them full-line comments (24%); line 1 is code so no header.
DENSE_SOURCE = """\
a01 = 1
# comment one
a02 = 2
a03 = 3
# comment two
a04 = 4
a05 = 5
# comment three
a06 = 6
a07 = 7
# comment four
a08 = 8
a09 = 9
# comment five
a10 = 10
a11 = 11
# comment six
a12 = 12
a13 = 13
a14 = 14
a15 = 15
a16 = 16
a17 = 17
a18 = 18
a19 = 19
"""

# 11 non-blank lines, 5 of them full-line comments (45%).
SHORT_DENSE_SOURCE = """\
a01 = 1
# comment one
a02 = 2
# comment two
a03 = 3
# comment three
a04 = 4
# comment four
a05 = 5
# comment five
a06 = 6
"""


def test_density_over_the_limit_fails_the_cli(tmp_path):
    source_path = tmp_path / 'dense.py'
    source_path.write_text(DENSE_SOURCE)

    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'comment-density', str(source_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert f'{source_path}: 6 of 25 lines are comments, limit 5 (10% + 3)' in result.stdout


def test_density_under_a_raised_limit_passes_the_cli(tmp_path):
    source_path = tmp_path / 'dense.py'
    source_path.write_text(DENSE_SOURCE)

    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'format_hooks.cli',
            'comment-density',
            '--max-share',
            '0.25',
            str(source_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_density_marker_skips_the_file(tmp_path):
    source_path = tmp_path / 'dense.py'
    source_path.write_text(DENSE_SOURCE + '# format-hooks: allow-comments\n')

    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'comment-density', str(source_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def run_density(source_path, *options):
    return subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'comment-density', *options, str(source_path)],
        capture_output=True,
        text=True,
    )


def test_short_dense_file_is_measured(tmp_path):
    source_path = tmp_path / 'short.py'
    source_path.write_text(SHORT_DENSE_SOURCE)

    result = run_density(source_path)

    assert result.returncode == 1
    assert f'{source_path}: 5 of 11 lines are comments, limit 4 (10% + 3)' in result.stdout


def test_one_line_file_that_is_all_docstring_passes(tmp_path):
    source_path = tmp_path / 'tiny.py'
    source_path.write_text('"""Holds the package version."""\n')

    result = run_density(source_path)

    assert result.returncode == 0


def test_small_file_within_the_fixed_allowance_passes(tmp_path):
    # 20 non-blank lines, 5 comments: 25%, but within 10% of 20 plus 3.
    source_path = tmp_path / 'small.py'
    source_path.write_text('value = 1\n' + '# comment\n' * 5 + 'value = 1\n' * 14)

    result = run_density(source_path)

    assert result.returncode == 0


def test_large_file_over_ten_percent_plus_the_allowance_fails(tmp_path):
    # 100 non-blank lines, 14 comments: the limit is 10% of 100 plus 3, so 13.
    source_path = tmp_path / 'large.py'
    source_path.write_text('value = 1\n' + '# comment\n' * 14 + 'value = 1\n' * 85)

    result = run_density(source_path)

    assert result.returncode == 1
    assert f'{source_path}: 14 of 100 lines are comments, limit 13 (10% + 3)' in result.stdout


def test_raised_allowance_passes_a_file_over_the_default(tmp_path):
    source_path = tmp_path / 'dense.py'
    source_path.write_text(DENSE_SOURCE)

    result = run_density(source_path, '--allowance-lines', '4')

    assert result.returncode == 0


def test_file_under_a_raised_line_floor_is_not_measured(tmp_path):
    source_path = tmp_path / 'short.py'
    source_path.write_text(SHORT_DENSE_SOURCE)

    result = run_density(source_path, '--min-lines', '20')

    assert result.returncode == 0


def test_license_header_is_not_counted():
    assert measure_comment_share('a.sh', '#!/bin/bash\n# License\nls\n# note\npwd\n') == (1, 3)


def test_module_docstring_counts():
    assert measure_comment_share('a.py', '"""Doc."""\nx = 1\n') == (1, 2)


def test_comment_at_the_end_of_a_code_line_does_not_count():
    assert measure_comment_share('a.py', 'x = 1\ny = 2  # why\n') == (0, 2)


def test_blank_line_ends_the_header():
    assert measure_comment_share('a.sh', '# License\n\n# note\nls\n') == (1, 2)


def test_block_comment_license_with_a_blank_line_is_all_header():
    source = '/* License\n\n   text */\nint a;\n// note\nint b;\n'

    assert measure_comment_share('a.c', source) == (1, 3)


def test_blank_line_inside_a_block_comment_is_not_counted():
    assert measure_comment_share('a.c', 'int a;\n/* one\n\n   two */\nint b;\n') == (2, 4)


def test_form_feed_does_not_count_as_a_line_break():
    assert measure_comment_share('a.py', 'x = 1\x0c\n# note\n') == (1, 2)


def test_unsupported_file_is_not_measured():
    assert measure_comment_share('a.md', '# Title\ntext\n') is None
