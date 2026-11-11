import subprocess
import sys

from format_hooks.comments import extract_comments
from format_hooks.pronouns import find_pronouns


def test_we_in_a_comment_is_flagged():
    assert find_pronouns(extract_comments('a.py', 'x = 1  # we expect this\n')) == [(1, 'we')]


def test_your_in_a_yaml_comment_is_flagged():
    comments = extract_comments('a.yaml', '# match your MAVROS build\nk: 1\n')

    assert find_pronouns(comments) == [(1, 'your')]


def test_capital_i_is_flagged():
    assert find_pronouns(extract_comments('a.py', '# here I check\n')) == [(1, 'I')]


def test_lowercase_i_is_not_flagged():
    assert find_pronouns(extract_comments('a.py', '# loop over i\n')) == []


def test_capitalized_we_is_flagged_as_written():
    assert find_pronouns(extract_comments('a.py', '# We will coerce\n')) == [(1, 'We')]


def test_pronoun_inside_a_longer_word_is_not_flagged():
    assert find_pronouns(extract_comments('a.py', '# use the mean of usable values\n')) == []


def test_capital_us_is_not_flagged():
    assert find_pronouns(extract_comments('a.py', '# US airspace rules\n')) == []


def test_lowercase_us_is_flagged():
    assert find_pronouns(extract_comments('a.py', '# tell us\n')) == [(1, 'us')]


def test_backticked_text_is_not_flagged():
    assert find_pronouns(extract_comments('a.py', '# label `you are here`\n')) == []


def test_pronoun_in_a_string_literal_is_not_flagged():
    assert find_pronouns(extract_comments('a.py', "label = 'we go'\n")) == []


def test_pronoun_in_a_docstring_is_flagged():
    comments = extract_comments('a.py', 'def f():\n    """Return what you asked for."""\n')

    assert find_pronouns(comments) == [(2, 'you')]


def test_straight_apostrophe_contraction_is_flagged():
    assert find_pronouns(extract_comments('a.py', "# let's go\n")) == [(1, "let's")]


def test_curly_apostrophe_contraction_is_flagged():
    assert find_pronouns(extract_comments('a.py', '# we’re done\n')) == [(1, 'we’re')]


def test_every_pronoun_on_a_line_is_flagged():
    comments = extract_comments('a.cpp', 'int a;  // you and me\n')

    assert find_pronouns(comments) == [(1, 'you'), (1, 'me')]


def test_cli_names_the_file_line_and_word(tmp_path):
    source_path = tmp_path / 'a.py'
    source_path.write_text('x = 1\ny = 2  # we expect this\n')

    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'comment-pronouns', str(source_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert f'{source_path}:2: personal pronoun "we" in comment' in result.stdout


def test_cli_passes_a_file_without_pronouns(tmp_path):
    source_path = tmp_path / 'a.py'
    source_path.write_text('x = 1  # set once\n')

    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'comment-pronouns', str(source_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_pronoun_marker_skips_the_file(tmp_path):
    source_path = tmp_path / 'a.py'
    source_path.write_text('# format-hooks: allow-pronouns\nx = 1  # we expect this\n')

    result = subprocess.run(
        [sys.executable, '-m', 'format_hooks.cli', 'comment-pronouns', str(source_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_i_in_i_slash_o_is_not_flagged():
    assert find_pronouns(extract_comments('a.py', '# blocking I/O here\n')) == []


def test_us_after_a_number_is_read_as_microseconds():
    assert find_pronouns(extract_comments('a.py', '# wait 500 us\n')) == []


def test_us_before_a_hyphen_is_not_flagged():
    assert find_pronouns(extract_comments('a.py', '# region us-east-1\n')) == []
