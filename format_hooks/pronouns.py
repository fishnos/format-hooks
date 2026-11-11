"""The `comment-pronouns` rule: personal pronouns in comments and docstrings.

Only reports; never edits a file.
"""

import argparse
import os
import re

from format_hooks.comments import LANGUAGE_BY_SUFFIX, Comment, extract_comments
from format_hooks.file_selection import select_files
from format_hooks.problems import Problem

ALLOW_MARKER = 'format-hooks: allow-pronouns'

_APOSTROPHE = "['’]"
_CONTRACTIONS = (
    ('I', 'm'),
    ('I', 've'),
    ('I', 'd'),
    ('I', 'll'),
    ('we', 're'),
    ('we', 've'),
    ('we', 'd'),
    ('we', 'll'),
    ('you', 're'),
    ('you', 've'),
    ('you', 'd'),
    ('you', 'll'),
    ('let', 's'),
)
_WORDS = (
    'I',
    'me',
    'my',
    'mine',
    'myself',
    'we',
    'us',
    'our',
    'ours',
    'ourselves',
    'you',
    'your',
    'yours',
    'yourself',
    'yourselves',
)
# Contractions come first so `we're` matches whole instead of stopping at `we`.
_PRONOUN = re.compile(
    r'(?<!\w)(?:'
    + '|'.join(f'{stem}{_APOSTROPHE}{ending}' for stem, ending in _CONTRACTIONS)
    + '|'
    + '|'.join(_WORDS)
    + r')(?!\w)',
    re.IGNORECASE,
)
_BACKTICKED = re.compile(r'`[^`]*`')
_NUMBER_BEFORE = re.compile(r'\d\s*$')


def _is_not_a_pronoun(word: str, text: str, start: int, end: int) -> bool:
    if word == 'i' or word == 'US':
        return True

    if word == 'I' and text.startswith('/', end):
        return True  # I/O

    # `500 us` is microseconds, `us-east-1` is a region.
    return word == 'us' and (
        text.startswith('-', end) or _NUMBER_BEFORE.search(text, 0, start) is not None
    )


def find_pronouns(comments: list[Comment]) -> list[tuple[int, str]]:
    found = []

    for comment in comments:
        text = _BACKTICKED.sub(' ', comment.text)
        for match in _PRONOUN.finditer(text):
            if not _is_not_a_pronoun(match.group(), text, match.start(), match.end()):
                found.append((comment.line, match.group()))

    return found


def check_file(path: str) -> list[Problem]:
    try:
        with open(path, encoding='utf-8') as file:
            source = file.read()
    except (OSError, UnicodeDecodeError):
        return []

    comments = extract_comments(path, source)
    if not comments or any(ALLOW_MARKER in comment.text for comment in comments):
        return []

    return [
        Problem(path, line, f'personal pronoun "{word}" in comment')
        for line, word in find_pronouns(comments)
    ]


def run(arguments: argparse.Namespace) -> int:
    paths = select_files(arguments.paths, tuple(LANGUAGE_BY_SUFFIX), os.getcwd())
    problems = [problem for path in paths for problem in check_file(path)]
    for problem in problems:
        print(problem.render())

    return 1 if problems else 0


def register(subparsers) -> None:
    parser = subparsers.add_parser('comment-pronouns', help='flag personal pronouns in comments')
    parser.add_argument('paths', nargs='*')
    parser.set_defaults(run=run)
