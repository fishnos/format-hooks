"""Shared formatter settings: report how a repository's copies drift, and sync them.

The ruff settings are compared key by key so each repository keeps its own
`ignore` and `extend-exclude` lists; the other shared files must match whole.
"""

import argparse
import dataclasses
import importlib.resources
import os
import re
import tomllib

from format_hooks.problems import Problem

RUFF_FILE_NAME = 'ruff.toml'
WHOLE_FILE_NAMES = ('.clang-format', '.prettierrc.json', '.editorconfig')
SHARED_RUFF_KEYS: tuple[tuple[str | None, str], ...] = (
    (None, 'line-length'),
    (None, 'target-version'),
    ('lint', 'select'),
    ('format', 'quote-style'),
)
MISSING_MESSAGE = 'missing; run format-hooks sync-config'
MISPLACED_MESSAGE = 'ruff settings live here; move them to ruff.toml'

_ABSENT = object()


def _read_shared_bytes(name: str) -> bytes:
    return (importlib.resources.files('format_hooks') / 'shared_config' / name).read_bytes()


def _read_bytes_or_none(path: str) -> bytes | None:
    try:
        with open(path, 'rb') as file:
            return file.read()
    except FileNotFoundError:
        return None


def _display_key(table: str | None, key: str) -> str:
    if table is None:
        return key

    return f'{table}.{key}'


def _lookup(settings: dict, table: str | None, key: str) -> object:
    if table is None:
        return settings.get(key, _ABSENT)

    table_settings = settings.get(table, {})
    if not isinstance(table_settings, dict):
        return _ABSENT

    return table_settings.get(key, _ABSENT)


def _differing_ruff_keys(repository_text: str) -> list[tuple[str | None, str]]:
    shared_settings = tomllib.loads(_read_shared_bytes(RUFF_FILE_NAME).decode())
    repository_settings = tomllib.loads(repository_text)

    return [
        (table, key)
        for table, key in SHARED_RUFF_KEYS
        if _lookup(repository_settings, table, key) != _lookup(shared_settings, table, key)
    ]


def find_misplaced_ruff_settings(repo_root: str) -> list[Problem]:
    """Ruff settings kept somewhere other than `ruff.toml`, which sync must not shadow."""

    problems = []

    if os.path.exists(os.path.join(repo_root, '.ruff.toml')):
        problems.append(Problem('.ruff.toml', None, MISPLACED_MESSAGE))

    pyproject_bytes = _read_bytes_or_none(os.path.join(repo_root, 'pyproject.toml'))
    if pyproject_bytes is not None:
        try:
            pyproject = tomllib.loads(pyproject_bytes.decode())
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            pyproject = {}

        if 'ruff' in pyproject.get('tool', {}):
            problems.append(Problem('pyproject.toml', None, MISPLACED_MESSAGE))

    return problems


def _find_ruff_drift(repo_root: str) -> list[Problem]:
    misplaced = find_misplaced_ruff_settings(repo_root)
    if misplaced:
        return misplaced

    repository_bytes = _read_bytes_or_none(os.path.join(repo_root, RUFF_FILE_NAME))
    if repository_bytes is None:
        return [Problem(RUFF_FILE_NAME, None, MISSING_MESSAGE)]

    try:
        differing_keys = _differing_ruff_keys(repository_bytes.decode())
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return [
            Problem(
                RUFF_FILE_NAME,
                None,
                'not valid TOML; fix it by hand, then run format-hooks sync-config',
            ),
        ]

    return [
        Problem(RUFF_FILE_NAME, None, f'{_display_key(table, key)} differs from format-hooks')
        for table, key in differing_keys
    ]


def find_drift(repo_root: str) -> list[Problem]:
    problems = _find_ruff_drift(repo_root)

    for name in WHOLE_FILE_NAMES:
        repository_bytes = _read_bytes_or_none(os.path.join(repo_root, name))
        if repository_bytes is None:
            problems.append(Problem(name, None, MISSING_MESSAGE))
        elif repository_bytes != _read_shared_bytes(name):
            problems.append(Problem(name, None, 'differs from format-hooks'))

    return problems


@dataclasses.dataclass(frozen=True)
class _Assignment:
    key_path: tuple[str, ...]
    value_start: int
    value_end: int


@dataclasses.dataclass
class _Section:
    """One table of a TOML file; the root table has an empty path."""

    path: tuple[str, ...]
    insertion_offset: int
    assignments: list[_Assignment] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    replacement: str


_TABLE_HEADER = re.compile(r'[ \t]*\[[ \t]*([^\[\]#]+?)[ \t]*\][ \t]*(#.*)?\r?$')
_ARRAY_TABLE_HEADER = re.compile(r'[ \t]*\[\[')
_ASSIGNMENT = re.compile(r'[ \t]*([A-Za-z0-9_\-."\' \t]+?)[ \t]*=')


def _split_key(dotted_key: str) -> tuple[str, ...]:
    return tuple(part.strip().strip('"\'') for part in dotted_key.split('.'))


def _string_end(text: str, start: int) -> int:
    """Return the offset just past the string literal that opens at `start`."""

    delimiter = text[start : start + 3]
    if delimiter not in ('"""', "'''"):
        delimiter = text[start]

    allows_escapes = delimiter[0] == '"'
    index = start + len(delimiter)
    while index < len(text):
        if allows_escapes and text[index] == '\\':
            index += 2
        elif text.startswith(delimiter, index):
            return index + len(delimiter)
        else:
            index += 1

    return len(text)


def _value_end(text: str, start: int) -> int:
    """Return the offset just past the value that starts after `=` at `start`.

    Trailing whitespace and a trailing comment are not part of the value, so a
    replacement keeps them.
    """

    bracket_depth = 0
    value_end = start
    index = start
    while index < len(text):
        character = text[index]
        if character in '"\'':
            index = _string_end(text, index)
            value_end = index
            continue

        if character == '#':
            line_end = text.find('\n', index)
            index = len(text) if line_end == -1 else line_end
            continue

        if character == '\n' and bracket_depth == 0 and value_end > start:
            break

        if character in '[{':
            bracket_depth += 1
        elif character in ']}':
            bracket_depth -= 1

        if not character.isspace():
            value_end = index + 1

        index += 1

    return value_end


def _line_end_after(text: str, offset: int) -> int:
    newline = text.find('\n', offset)

    return len(text) if newline == -1 else newline + 1


def _scan_sections(text: str) -> list[_Section]:
    sections = [_Section(path=(), insertion_offset=0)]
    offset = 0
    while offset < len(text):
        line_end = _line_end_after(text, offset)
        line = text[offset:line_end].rstrip('\n')
        header = _TABLE_HEADER.match(line)
        assignment = _ASSIGNMENT.match(line)

        if _ARRAY_TABLE_HEADER.match(line):
            sections.append(_Section(path=('[[array table]]',), insertion_offset=line_end))
        elif header:
            sections.append(_Section(path=_split_key(header.group(1)), insertion_offset=line_end))
        elif assignment:
            value_start = offset + assignment.end()
            while text[value_start : value_start + 1] in (' ', '\t'):
                value_start += 1

            value_end = _value_end(text, value_start)
            sections[-1].assignments.append(
                _Assignment(_split_key(assignment.group(1)), value_start, value_end),
            )
            line_end = _line_end_after(text, value_end)
            sections[-1].insertion_offset = line_end

        offset = line_end

    return sections


def _render_value(value: object) -> str:
    if isinstance(value, str):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')

        return f'"{escaped}"'

    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)

    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return '[' + ', '.join(_render_value(item) for item in value) + ']'

    raise TypeError(f'no TOML writer for {value!r}')


def _sync_ruff_text(text: str) -> str:
    differing_keys = _differing_ruff_keys(text)
    if not differing_keys:
        return text

    shared_settings = tomllib.loads(_read_shared_bytes(RUFF_FILE_NAME).decode())
    newline = '\r\n' if '\r\n' in text else '\n'
    sections = _scan_sections(text)
    root_section = sections[0]
    edits: list[_Edit] = []
    new_tables: dict[str, list[str]] = {}

    for table, key in differing_keys:
        rendered_value = _render_value(_lookup(shared_settings, table, key))
        table_path = () if table is None else (table,)
        full_path = (*table_path, key)
        existing = [
            assignment
            for section in sections
            for assignment in section.assignments
            if (*section.path, *assignment.key_path) == full_path
        ]
        table_sections = [section for section in sections if section.path == table_path]
        uses_dotted_keys = any(
            assignment.key_path[: len(table_path)] == table_path
            for assignment in root_section.assignments
            if len(assignment.key_path) > 1
        )

        if existing:
            edits.append(_Edit(existing[0].value_start, existing[0].value_end, rendered_value))
        elif table_sections:
            edits.append(_insertion(text, table_sections[0], f'{key} = {rendered_value}', newline))
        elif uses_dotted_keys:
            line = f'{table}.{key} = {rendered_value}'
            edits.append(_insertion(text, root_section, line, newline))
        else:
            new_tables.setdefault(table, []).append(f'{key} = {rendered_value}')

    pieces = []
    cursor = 0

    for edit in sorted(edits, key=lambda edit: edit.start):
        pieces.append(text[cursor : edit.start])
        pieces.append(edit.replacement)
        cursor = edit.end

    pieces.append(text[cursor:])
    synced_text = ''.join(pieces)

    for table, lines in new_tables.items():
        if synced_text and not synced_text.endswith('\n'):
            synced_text += newline

        if synced_text:
            synced_text += newline

        synced_text += f'[{table}]{newline}' + ''.join(line + newline for line in lines)

    return synced_text


def _insertion(text: str, section: _Section, line: str, newline: str) -> _Edit:
    offset = section.insertion_offset
    prefix = newline if offset == len(text) and text and not text.endswith('\n') else ''

    return _Edit(offset, offset, prefix + line + newline)


def _write_bytes(path: str, content: bytes) -> None:
    with open(path, 'wb') as file:
        file.write(content)


def _sync_ruff_file(repo_root: str) -> bool:
    """Bring `ruff.toml` in line; return whether it was written."""

    if find_misplaced_ruff_settings(repo_root):
        return False

    ruff_path = os.path.join(repo_root, RUFF_FILE_NAME)
    repository_bytes = _read_bytes_or_none(ruff_path)
    if repository_bytes is None:
        _write_bytes(ruff_path, _read_shared_bytes(RUFF_FILE_NAME))

        return True

    try:
        repository_text = repository_bytes.decode()
        synced_text = _sync_ruff_text(repository_text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False

    if synced_text == repository_text:
        return False

    _write_bytes(ruff_path, synced_text.encode())

    return True


def sync_config(repo_root: str) -> list[str]:
    rewritten_names = [RUFF_FILE_NAME] if _sync_ruff_file(repo_root) else []

    for name in WHOLE_FILE_NAMES:
        path = os.path.join(repo_root, name)
        shared_bytes = _read_shared_bytes(name)
        if _read_bytes_or_none(path) != shared_bytes:
            _write_bytes(path, shared_bytes)
            rewritten_names.append(name)

    return rewritten_names


def _run_config_drift(arguments: argparse.Namespace) -> int:
    problems = find_drift(os.getcwd())
    for problem in problems:
        print(problem.render())

    return 1 if problems else 0


def _run_sync_config(arguments: argparse.Namespace) -> int:
    for name in sync_config(os.getcwd()):
        print(f'synced {name}')

    misplaced = find_misplaced_ruff_settings(os.getcwd())
    for problem in misplaced:
        print(problem.render())

    return 1 if misplaced else 0


def register(subparsers: argparse._SubParsersAction) -> None:
    drift_parser = subparsers.add_parser(
        'config-drift',
        help='report shared formatter settings that differ in the current repository',
    )
    drift_parser.set_defaults(run=_run_config_drift)
    sync_parser = subparsers.add_parser(
        'sync-config',
        help='rewrite the shared formatter settings in the current repository to match',
    )
    sync_parser.set_defaults(run=_run_sync_config)
