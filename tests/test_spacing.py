import subprocess
import sys

from format_hooks.spacing import find_spacing_problems, respace


def test_return_after_a_statement_gets_a_blank_line_above():
    source = 'def f(x):\n    y = x\n    return y\n'

    assert respace(source) == 'def f(x):\n    y = x\n\n    return y\n'


def test_raise_after_a_statement_gets_a_blank_line_above():
    source = 'def f(x):\n    log(x)\n    raise ValueError\n'

    assert respace(source) == 'def f(x):\n    log(x)\n\n    raise ValueError\n'


def test_return_first_in_its_block_gets_no_blank_line():
    assert find_spacing_problems('def f(x):\n    if x:\n        return 1\n') == []


def test_blank_line_after_a_block_header_is_removed():
    assert respace('def f():\n\n    pass\n') == 'def f():\n    pass\n'


def test_two_blank_lines_inside_a_function_collapse_to_one():
    source = 'def f():\n    a = 1\n\n\n    b = 2\n'

    assert respace(source) == 'def f():\n    a = 1\n\n    b = 2\n'


def test_blank_line_before_else_is_removed():
    assert respace('if x:\n    a()\n\nelse:\n    b()\n') == 'if x:\n    a()\nelse:\n    b()\n'


def test_blank_line_before_elif_is_reported_with_its_keyword():
    source = 'if x:\n    a()\n\nelif y:\n    b()\n'

    assert find_spacing_problems(source) == [(4, 'no blank line allowed before elif')]


def test_blank_line_before_except_is_removed():
    source = 'try:\n    a()\n\nexcept OSError:\n    b()\n'

    assert respace(source) == 'try:\n    a()\nexcept OSError:\n    b()\n'


def test_blank_line_before_case_is_removed():
    source = 'match x:\n    case 1:\n        a()\n\n    case _:\n        b()\n'

    assert respace(source) == 'match x:\n    case 1:\n        a()\n    case _:\n        b()\n'


def test_comment_above_a_return_moves_with_it():
    source = 'def f():\n    a = 1\n    # why\n    return a\n'

    assert respace(source) == 'def f():\n    a = 1\n\n    # why\n    return a\n'


def test_gap_with_a_detached_comment_is_left_alone():
    source = 'def f():\n    a = 1\n\n    # note\n\n    return a\n'

    assert respace(source) == source


def test_gap_with_a_detached_comment_is_not_reported():
    source = 'def f():\n    a = 1\n\n    # note\n\n\n    return a\n'

    assert find_spacing_problems(source) == []


def test_comment_indented_under_the_block_above_does_not_move_with_the_return():
    source = 'def f(x):\n    for a in x:\n        use(a)\n        # end of loop\n    return x\n'

    assert respace(source) == source


def test_problem_reports_the_line_of_the_return():
    source = 'def f(x):\n    y = x\n    return y\n'

    assert find_spacing_problems(source) == [(3, 'blank line needed before return')]


def test_unparseable_source_is_left_unchanged():
    assert respace('def f(:\n  return\n') == 'def f(:\n  return\n'


def test_unparseable_source_reports_nothing():
    assert find_spacing_problems('def f(:\n  y = 1\n  return y\n') == []


def test_python_2_source_is_left_unchanged():
    source = 'def f():\n    x = 1\n    print "x"\n    return x\n'

    assert respace(source) == source


def test_crlf_and_missing_final_newline_are_kept():
    source = 'def f(x):\r\n    y = x\r\n    return y'

    assert respace(source) == 'def f(x):\r\n    y = x\r\n\r\n    return y'


def test_blank_lines_inside_a_multiline_string_are_not_a_gap():
    source = 'def f():\n    a = """\n\n\n"""\n    return a\n'

    assert respace(source) == 'def f():\n    a = """\n\n\n"""\n\n    return a\n'


def test_return_after_a_semicolon_is_left_alone():
    source = 'def f():\n    a = 1; return a\n'

    assert respace(source) == source


def test_code_after_a_block_gets_a_blank_line():
    source = 'def f(x):\n    if x:\n        a()\n    b()\n'

    assert respace(source) == 'def f(x):\n    if x:\n        a()\n\n    b()\n'


def test_block_after_a_statement_gets_a_blank_line():
    source = 'def f(x):\n    a()\n    if x:\n        b()\n'

    assert respace(source) == 'def f(x):\n    a()\n\n    if x:\n        b()\n'


def test_assignment_stays_with_the_loop_over_it():
    source = 'def f():\n    items = load()\n\n    for item in items:\n        use(item)\n'

    assert (
        respace(source)
        == 'def f():\n    items = load()\n    for item in items:\n        use(item)\n'
    )


def test_assignment_split_from_its_block_is_reported():
    source = 'def f():\n    items = load()\n\n    for item in items:\n        use(item)\n'

    assert find_spacing_problems(source) == [
        (4, 'no blank line allowed between assignment and the block that uses it'),
    ]


def test_attribute_assignment_stays_with_the_test_on_it():
    source = 'def f(self):\n    self.ready = check()\n    if self.ready:\n        go()\n'

    assert respace(source) == source


def test_tuple_assignment_stays_with_the_test_on_one_of_its_names():
    source = 'def f():\n    first, rest = split()\n    if rest:\n        go()\n'

    assert respace(source) == source


def test_assignment_of_an_unrelated_name_is_separated_from_the_block():
    source = 'def f(x):\n    y = 1\n    if x:\n        go(y)\n'

    assert respace(source) == 'def f(x):\n    y = 1\n\n    if x:\n        go(y)\n'


def test_try_after_an_assignment_gets_a_blank_line_because_try_has_no_header():
    source = (
        'def f():\n    path = find()\n'
        '    try:\n        open(path)\n    except OSError:\n        pass\n'
    )

    assert respace(source) == (
        'def f():\n    path = find()\n\n'
        '    try:\n        open(path)\n    except OSError:\n        pass\n'
    )


def test_consecutive_guards_are_separated():
    source = 'def f(x):\n    if not x:\n        return\n    if x < 0:\n        raise ValueError\n'

    assert respace(source) == (
        'def f(x):\n    if not x:\n        return\n\n    if x < 0:\n        raise ValueError\n'
    )


def test_code_after_a_docstring_gets_a_blank_line():
    assert respace('def f():\n    """Doc."""\n    a()\n') == 'def f():\n    """Doc."""\n\n    a()\n'


def test_code_after_a_class_docstring_gets_a_blank_line():
    source = 'class A:\n    """Doc."""\n    size = 1\n'

    assert respace(source) == 'class A:\n    """Doc."""\n\n    size = 1\n'


def test_nested_def_after_a_statement_is_not_treated_as_a_block():
    source = 'def f():\n    a = 1\n    def g():\n        pass\n'

    assert respace(source) == source


def test_top_level_loop_follows_the_block_rules():
    source = 'import sys\nfor arg in sys.argv:\n    print(arg)\nprint(1)\n'

    assert respace(source) == 'import sys\n\nfor arg in sys.argv:\n    print(arg)\n\nprint(1)\n'


def test_two_blank_lines_before_a_top_level_def_are_left_to_ruff():
    source = 'import os\n\n\ndef f():\n    pass\n'

    assert respace(source) == source


def test_top_level_block_right_after_a_decorated_def_is_left_to_ruff():
    source = '@cache\ndef f():\n    pass\nif x:\n    f()\n'

    assert respace(source) == source


def test_two_blank_lines_before_a_top_level_block_are_kept():
    source = 'import sys\n\n\nif sys.argv:\n    print(1)\n'

    assert respace(source) == source


RUFF_SETTINGS = 'line-length = 100\n\n[format]\nquote-style = "single"\n'

SOURCE_WITH_EVERY_RULE = '''"""Module doc."""
import sys
def guard(values, state):
    """Check values."""
    if not values: return
    if len(values) > 9: raise ValueError
    items = list(values)

    for item in items:
        print(item)
    total = 0
    # running sum
    for item in items:
        total += item
    state.ready = total > 0
    if state.ready:
        print(total)
    try:
        open('a')

    except OSError:
        pass
    class Inner:
        """Inner doc."""
        size = 1
    def helper():

        return 1


    return total
for arg in sys.argv:
    print(arg)
print(1)
if __name__ == '__main__':
    guard(sys.argv, None)
'''


def _ruff(*arguments, cwd):
    return subprocess.run(
        [sys.executable, '-m', 'ruff', *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _ruff_format_then_respace(source_path):
    _ruff('format', str(source_path), cwd=source_path.parent)
    source_path.write_text(respace(source_path.read_text()))

    return source_path.read_text()


def test_ruff_format_then_respace_is_stable(tmp_path):
    (tmp_path / 'ruff.toml').write_text(RUFF_SETTINGS)
    source_path = tmp_path / 'module.py'
    source_path.write_text(SOURCE_WITH_EVERY_RULE)

    first_round = _ruff_format_then_respace(source_path)
    second_round = _ruff_format_then_respace(source_path)

    assert second_round == first_round


def test_ruff_format_leaves_respaced_output_alone(tmp_path):
    (tmp_path / 'ruff.toml').write_text(RUFF_SETTINGS)
    source_path = tmp_path / 'module.py'
    source_path.write_text(SOURCE_WITH_EVERY_RULE)
    respaced = _ruff_format_then_respace(source_path)

    _ruff('format', str(source_path), cwd=tmp_path)

    assert source_path.read_text() == respaced


def test_ruff_splits_a_one_line_guard(tmp_path):
    (tmp_path / 'ruff.toml').write_text(RUFF_SETTINGS)
    source_path = tmp_path / 'module.py'
    source_path.write_text('def f(x):\n    if x: return\n    return 1\n')

    _ruff('format', str(source_path), cwd=tmp_path)

    assert '    if x:\n        return\n' in source_path.read_text()


def test_blank_line_ruff_puts_before_a_class_opening_an_except_block_is_kept():
    source = 'try:\n    import a\nexcept ImportError:\n\n    class A(Exception):\n        pass\n'

    assert respace(source) == source


def test_blank_line_ruff_puts_before_a_def_opening_an_if_block_is_kept():
    source = 'if x:\n\n    def f():\n        return 1\n'

    assert find_spacing_problems(source) == []


def test_blank_line_before_a_def_opening_a_function_body_is_still_removed():
    source = 'def outer():\n\n    def f():\n        return 1\n\n    return f\n'

    assert respace(source) == 'def outer():\n    def f():\n        return 1\n\n    return f\n'


def test_string_whose_last_line_starts_with_a_hash_is_left_unchanged():
    source = 'def f():\n    a = """\n    # x"""\n    return a\n'

    assert respace(source) == 'def f():\n    a = """\n    # x"""\n\n    return a\n'


def test_fstring_whose_last_line_starts_with_a_hash_is_left_unchanged():
    source = 'def f(b):\n    a = f"""{b}\n    # x"""\n    return a\n'

    assert respace(source) == 'def f(b):\n    a = f"""{b}\n    # x"""\n\n    return a\n'
