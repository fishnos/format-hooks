from format_hooks.comments import LANGUAGE_BY_SUFFIX, Comment, extract_comments


def test_python_inline_comment_is_not_full_line():
    assert extract_comments('a.py', 'x = 1  # set\n') == [Comment(1, 'set', False, False)]


def test_python_comment_alone_on_its_line_is_full_line():
    assert extract_comments('a.py', '    # set\nx = 1\n') == [Comment(1, 'set', True, False)]


def test_python_docstring_lines_are_comments():
    comments = extract_comments('a.py', 'def f():\n    """One.\n\n    Two.\n    """\n')

    assert [comment.line for comment in comments] == [2, 3, 4, 5]


def test_python_docstring_lines_are_marked_as_docstring():
    comments = extract_comments('a.py', '"""Doc."""\nx = 1\n')

    assert comments == [Comment(1, 'Doc.', True, True)]


def test_python_string_that_is_not_a_docstring_is_not_a_comment():
    assert extract_comments('a.py', 'x = 1\n"""Not a docstring."""\n') == []


def test_python_form_feed_does_not_shift_line_lookup():
    assert extract_comments('a.py', 'x = 1\x0c\ny = 2  # why\n') == [
        Comment(2, 'why', False, False),
    ]


def test_c_form_feed_does_not_count_as_a_line_break():
    assert extract_comments('a.c', 'int a;\x0c\n// why\n') == [Comment(2, 'why', True, False)]


def test_python_that_does_not_tokenize_returns_none():
    assert extract_comments('a.py', 'x = (\n') is None


def test_python_2_source_returns_none():
    assert extract_comments('a.py', 'print "hello"  # we go\n') is None


def test_hash_inside_shell_string_is_not_a_comment():
    assert extract_comments('a.sh', 'echo "a # b"\n') == []


def test_hash_inside_single_quoted_shell_string_is_not_a_comment():
    assert extract_comments('a.sh', "echo 'a # b'\n") == []


def test_shell_comment_alone_on_its_line_is_full_line():
    assert extract_comments('a.sh', '  # note\nls\n') == [Comment(1, 'note', True, False)]


def test_hash_inside_yaml_quoted_value_is_not_a_comment():
    assert extract_comments('a.yaml', 'url: "x#y"  # real\n') == [Comment(1, 'real', False, False)]


def test_toml_comment_is_found():
    assert extract_comments('a.toml', 'key = 1  # why\n') == [Comment(1, 'why', False, False)]


def test_block_comment_spans_lines_in_cpp():
    comments = extract_comments('a.cpp', 'int a; /* one\ntwo */ int b;\n')

    assert [comment.line for comment in comments] == [1, 2]


def test_block_comment_line_with_code_after_it_is_not_full_line():
    comments = extract_comments('a.cpp', 'int a; /* one\ntwo */ int b;\n')

    assert comments[1] == Comment(2, 'two', False, False)


def test_line_inside_a_block_comment_is_full_line():
    comments = extract_comments('a.c', '/* one\n   two\n*/\nint a;\n')

    assert comments[1] == Comment(2, 'two', True, False)


def test_opening_marker_alone_on_its_line_is_a_comment_line():
    comments = extract_comments('a.cpp', '/*\n * one\n */\nint a;\n')

    assert [comment.line for comment in comments] == [1, 2, 3]


def test_double_slash_comment_after_code_is_not_full_line():
    assert extract_comments('a.js', 'let a = 1; // why\n') == [Comment(1, 'why', False, False)]


def test_slashes_inside_a_typescript_string_are_not_a_comment():
    assert extract_comments('a.ts', "const url = 'http://x';\n") == []


def test_slashes_inside_a_backtick_string_are_not_a_comment():
    assert extract_comments('a.ts', 'const url = `http://x`;\n') == []


def test_unsupported_suffix_returns_none():
    assert extract_comments('a.md', '# Title\n') is None


def test_header_files_use_the_c_family_scanner():
    assert LANGUAGE_BY_SUFFIX['.hpp'] == 'c_family'
