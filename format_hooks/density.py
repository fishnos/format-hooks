"""The `comment-density` rule: the share of a file's lines that are comments.

Comment lines are full-line comments plus docstring lines. The header at the
top of a file (a shebang and the comment run under it, such as a license) is
left out of both counts, so a long license does not trip the limit. Only
reports; never edits a file.
"""

import argparse
import os

from format_hooks.comments import LANGUAGE_BY_SUFFIX, extract_comments, split_lines
from format_hooks.file_selection import select_files
from format_hooks.problems import Problem

ALLOW_MARKER = 'format-hooks: allow-comments'


def measure_comment_share(path: str, source: str) -> tuple[int, int] | None:
    comments = extract_comments(path, source)
    if comments is None:
        return None

    lines = split_lines(source)
    non_blank_lines = {number for number, line in enumerate(lines, start=1) if line.strip()}
    header_candidates = {
        comment.line for comment in comments if comment.is_full_line and not comment.is_docstring
    }

    if lines and lines[0].startswith('#!'):
        header_candidates.add(1)

    header_end = 0
    while header_end + 1 in header_candidates:
        header_end += 1

    comment_lines = {
        comment.line for comment in comments if comment.is_full_line or comment.is_docstring
    }
    body_lines = {number for number in non_blank_lines if number > header_end}

    return len(comment_lines & body_lines), len(body_lines)


def check_file(path: str, max_share: float, min_lines: int) -> list[Problem]:
    try:
        with open(path, encoding='utf-8') as file:
            source = file.read()
    except (OSError, UnicodeDecodeError):
        return []

    comments = extract_comments(path, source)
    if comments is None or any(ALLOW_MARKER in comment.text for comment in comments):
        return []

    comment_count, line_count = measure_comment_share(path, source)
    if line_count == 0 or line_count < min_lines:
        return []

    share = comment_count / line_count
    if share <= max_share:
        return []

    return [Problem(path, None, f'{share:.0%} comment lines, limit {max_share:.0%}')]


def run(arguments: argparse.Namespace) -> int:
    paths = select_files(arguments.paths, tuple(LANGUAGE_BY_SUFFIX), os.getcwd())
    problems = [
        problem
        for path in paths
        for problem in check_file(path, arguments.max_share, arguments.min_lines)
    ]
    for problem in problems:
        print(problem.render())

    return 1 if problems else 0


def register(subparsers) -> None:
    parser = subparsers.add_parser('comment-density', help='limit the share of comment lines')
    parser.add_argument('--max-share', type=float, default=0.20)
    parser.add_argument('--min-lines', type=int, default=20)
    parser.add_argument('paths', nargs='*')
    parser.set_defaults(run=run)
