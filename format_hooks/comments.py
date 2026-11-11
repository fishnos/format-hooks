"""Comments and docstrings, one record per physical line, for every supported language.

Python is read with `tokenize` and `ast`, so only real comments and docstrings
count. The other languages use a small line scanner that knows about quotes, so
a comment marker inside a string literal is not taken for a comment.
"""

import ast
import dataclasses
import io
import os
import re
import tokenize

LANGUAGE_BY_SUFFIX: dict[str, str] = {
    '.py': 'python',
    '.sh': 'hash',
    '.bash': 'hash',
    '.yaml': 'hash',
    '.yml': 'hash',
    '.toml': 'hash',
    '.c': 'c_family',
    '.h': 'c_family',
    '.cc': 'c_family',
    '.cpp': 'c_family',
    '.cxx': 'c_family',
    '.hpp': 'c_family',
    '.hh': 'c_family',
    '.ts': 'c_family',
    '.tsx': 'c_family',
    '.js': 'c_family',
    '.jsx': 'c_family',
    '.mjs': 'c_family',
    '.cjs': 'c_family',
}

_DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
_DOCSTRING_OPENING = re.compile(r'^[rRuU]?("""|\'\'\'|"|\')')
_DOCSTRING_CLOSING = re.compile(r'("""|\'\'\'|"|\')$')


@dataclasses.dataclass(frozen=True)
class Comment:
    line: int
    text: str
    is_full_line: bool
    is_docstring: bool


def extract_comments(path: str, source: str) -> list[Comment] | None:
    language = LANGUAGE_BY_SUFFIX.get(os.path.splitext(path)[1])
    if language == 'python':
        return _extract_python(source)

    if language == 'hash':
        return _scan_lines(source, _scan_hash_line)

    if language == 'c_family':
        return _scan_lines(source, _scan_c_family_line)

    return None


def split_lines(source: str) -> list[str]:
    """Splits on line endings only.

    `str.splitlines` also breaks on form feeds and other separators that
    `tokenize` and editors treat as ordinary characters, which shifts line numbers.
    """

    return re.split(r'\r\n|\r|\n', source.removesuffix('\n').removesuffix('\r'))


def _extract_python(source: str) -> list[Comment] | None:
    lines = split_lines(source)

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        tree = ast.parse(source)
    except (SyntaxError, tokenize.TokenError):
        return None

    comments = []

    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue

        line_number, column = token.start
        is_full_line = not lines[line_number - 1][:column].strip()
        comments.append(Comment(line_number, token.string[1:].strip(), is_full_line, False))

    for node in ast.walk(tree):
        if not isinstance(node, _DOCSTRING_OWNERS) or not node.body:
            continue

        first = node.body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            continue

        for line_number in range(first.lineno, first.end_lineno + 1):
            text = _DOCSTRING_OPENING.sub('', lines[line_number - 1].strip())
            text = _DOCSTRING_CLOSING.sub('', text).strip()
            comments.append(Comment(line_number, text, True, True))

    return sorted(comments, key=lambda comment: comment.line)


def _scan_lines(source, scan_line) -> list[Comment]:
    comments = []
    in_block_comment = False

    for line_number, line in enumerate(split_lines(source), start=1):
        comment_parts, has_code, in_block_comment = scan_line(line, in_block_comment)
        if comment_parts:
            text = ' '.join(part.strip() for part in comment_parts if part.strip())
            comments.append(Comment(line_number, text, not has_code, False))

    return comments


def _scan_hash_line(line: str, in_block_comment: bool) -> tuple[list[str], bool, bool]:
    quote = None
    index = 0
    while index < len(line):
        character = line[index]

        if quote:
            if character == '\\' and quote == '"':
                index += 1
            elif character == quote:
                quote = None
        elif character == '\\':
            index += 1
        elif character in '\'"':
            quote = character
        elif character == '#' and (index == 0 or line[index - 1].isspace()):
            return [line[index + 1 :]], bool(line[:index].strip()), False

        index += 1

    return [], bool(line.strip()), False


def _scan_c_family_line(line: str, in_block_comment: bool) -> tuple[list[str], bool, bool]:
    comment_parts = []
    has_code = False
    quote = None
    index = 0
    while index < len(line):
        if in_block_comment:
            end = line.find('*/', index)
            if end == -1:
                comment_parts.append(line[index:])

                return comment_parts, has_code, True

            comment_parts.append(line[index:end])
            in_block_comment = False
            index = end + 2
            continue

        character = line[index]

        if quote:
            if character == '\\':
                index += 1
            elif character == quote:
                quote = None
        elif line.startswith('//', index):
            comment_parts.append(line[index + 2 :])

            return comment_parts, has_code, False
        elif line.startswith('/*', index):
            in_block_comment = True
            index += 2
            continue
        elif character in '\'"`':
            quote = character
            has_code = True
        elif not character.isspace():
            has_code = True

        index += 1

    if in_block_comment:
        comment_parts.append('')

    return comment_parts, has_code, in_block_comment
