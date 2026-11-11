"""Python spacing rules: where blank lines go between statements.

Every gap between two sibling statements, or between a block header and its
first statement, gets one decision. The pass only adds or removes blank lines,
so it never changes what the code does.
"""

import argparse
import ast
import dataclasses
import enum
import io
import os
import re
import tokenize
import warnings

from format_hooks.file_selection import select_files
from format_hooks.problems import Problem

_CLAUSE_HEADER = re.compile(r'\s*(elif|else|except|finally|case)\b')
_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_BLOCKS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.TryStar,
    ast.Match,
)


class _Decision(enum.Enum):
    REQUIRE = enum.auto()
    FORBID = enum.auto()
    KEEP = enum.auto()


@dataclasses.dataclass(frozen=True)
class _Rule:
    decision: _Decision
    message: str = ''


@dataclasses.dataclass(frozen=True)
class _Fix:
    """A gap whose blank-line count breaks its rule."""

    first_blank_index: int
    blank_count: int
    target_count: int
    line: int
    message: str


class _Lines:
    """The source split into physical lines, classified the way gaps need.

    Lines after the first line of a multi-line string count as code, so a
    string line that is blank or starts with `#` is never moved or removed.
    """

    def __init__(self, source: str):
        self.text = io.StringIO(source, newline='').readlines()
        self.string_lines = _string_continuation_lines(source)

    def is_blank(self, index: int) -> bool:
        return index not in self.string_lines and not self.text[index].strip()

    def is_comment(self, index: int) -> bool:
        return index not in self.string_lines and self.text[index].lstrip().startswith('#')

    def indent(self, index: int) -> int:
        line = self.text[index]

        return len(line) - len(line.lstrip())

    def newline(self) -> str:
        for line in self.text:
            if line.endswith('\r\n'):
                return '\r\n'

            if line.endswith(('\n', '\r')):
                return line[-1]

        return '\n'


def _string_continuation_lines(source: str) -> set[int]:
    """Zero-based indexes of the lines a string continues onto past its first line."""

    lines: set[int] = set()
    fstring_starts: list[int] = []

    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.FSTRING_START:
                fstring_starts.append(token.start[0])
            elif token.type == tokenize.FSTRING_END:
                lines.update(range(fstring_starts.pop(), token.end[0]))
            elif token.type == tokenize.STRING:
                lines.update(range(token.start[0], token.end[0]))
    except (tokenize.TokenError, SyntaxError):
        return lines

    return lines


def _parse(source: str) -> ast.Module | None:
    # Invalid escape sequences warn at parse time; the warning is not a spacing problem.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', SyntaxWarning)

        try:
            return ast.parse(source)
        except (SyntaxError, ValueError):
            return None


class _Planner:
    """Walks every statement list and records each gap that breaks its rule."""

    def __init__(self, lines: _Lines):
        self.lines = lines
        self.fixes: list[_Fix] = []

    def visit_body(
        self,
        statements: list[ast.stmt],
        is_module: bool,
        is_definition_body: bool = False,
    ) -> None:
        for index, statement in enumerate(statements):
            previous = statements[index - 1] if index else None
            follows_docstring = is_definition_body and index == 1 and _is_docstring(previous)
            rule = _decide(previous, statement, follows_docstring, is_module, is_definition_body)
            self._check_statement_gap(statement, rule, is_module)
            self.visit_children(statement)

    def visit_children(self, node: ast.stmt) -> None:
        if isinstance(node, _DEFINITIONS):
            self.visit_body(node.body, is_module=False, is_definition_body=True)
        elif isinstance(node, ast.If):
            self.visit_body(node.body, is_module=False)
            self._visit_if_orelse(node)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            self.visit_body(node.body, is_module=False)
            self._visit_clause('else', node.body, node.orelse)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            self.visit_body(node.body, is_module=False)
        elif isinstance(node, (ast.Try, ast.TryStar)):
            self._visit_try(node)
        elif isinstance(node, ast.Match):
            self._visit_match(node)

    def _visit_if_orelse(self, node: ast.If) -> None:
        orelse = node.orelse
        is_elif = (
            len(orelse) == 1
            and isinstance(orelse[0], ast.If)
            and self.lines.text[orelse[0].lineno - 1].lstrip().startswith('elif')
        )
        if is_elif:
            self._check_clause_gap('elif', orelse[0].lineno - 1)
            self.visit_children(orelse[0])

            return

        self._visit_clause('else', node.body, orelse)

    def _visit_try(self, node: ast.Try | ast.TryStar) -> None:
        self.visit_body(node.body, is_module=False)
        section = node.body

        for handler in node.handlers:
            self._check_clause_gap('except', handler.lineno - 1)
            self.visit_body(handler.body, is_module=False)
            section = handler.body

        if node.orelse:
            self._visit_clause('else', section, node.orelse)
            section = node.orelse

        self._visit_clause('finally', section, node.finalbody)

    def _visit_match(self, node: ast.Match) -> None:
        previous_end = node.subject.end_lineno

        for case in node.cases:
            header_index = self._next_code_index(previous_end)
            if header_index is not None:
                self._check_clause_gap('case', header_index)

            self.visit_body(case.body, is_module=False)
            previous_end = case.body[-1].end_lineno

    def _visit_clause(self, keyword: str, previous: list[ast.stmt], body: list[ast.stmt]) -> None:
        if not body:
            return

        header_index = self._next_code_index(previous[-1].end_lineno)
        if header_index is not None:
            self._check_clause_gap(keyword, header_index)

        self.visit_body(body, is_module=False)

    def _next_code_index(self, after_line: int) -> int | None:
        index = after_line
        while index < len(self.lines.text) and (
            self.lines.is_blank(index) or self.lines.is_comment(index)
        ):
            index += 1

        if index >= len(self.lines.text) or not _CLAUSE_HEADER.match(self.lines.text[index]):
            return None

        return index

    def _check_clause_gap(self, keyword: str, header_index: int) -> None:
        rule = _Rule(_Decision.FORBID, f'no blank line allowed before {keyword}')
        self._check_gap(header_index, header_index + 1, rule, is_module=False)

    def _check_statement_gap(self, statement: ast.stmt, rule: _Rule, is_module: bool) -> None:
        first_line = min(
            [statement.lineno] + [decorator.lineno for decorator in _decorators(statement)],
        )
        line_bytes = self.lines.text[statement.lineno - 1].encode('utf-8')
        starts_its_line = not line_bytes[: statement.col_offset].strip()
        if first_line == statement.lineno and not starts_its_line:
            return

        self._check_gap(first_line - 1, first_line, rule, is_module)

    def _check_gap(self, start_index: int, report_line: int, rule: _Rule, is_module: bool) -> None:
        """Measures the blank run above `start_index` and records a fix if it breaks `rule`.

        Comment lines directly above, at the same indentation, belong to the
        statement and move with it. Any other comment line in the gap means
        its spacing was chosen by hand, so the gap is left alone.
        """

        indent = self.lines.indent(start_index)
        index = start_index - 1
        while index >= 0 and self.lines.is_comment(index) and self.lines.indent(index) == indent:
            index -= 1

        insertion_index = index + 1

        while index >= 0 and self.lines.is_blank(index):
            index -= 1

        if index >= 0 and self.lines.is_comment(index):
            return

        first_blank_index = index + 1
        blank_count = insertion_index - first_blank_index
        target_count, message = _target(rule, blank_count, is_module)
        if target_count != blank_count:
            self.fixes.append(
                _Fix(first_blank_index, blank_count, target_count, report_line, message),
            )


def _decorators(statement: ast.stmt) -> list[ast.expr]:
    return getattr(statement, 'decorator_list', [])


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _target_texts(statement: ast.stmt) -> set[str]:
    """Source text of each name or attribute an assignment binds, tuples unpacked."""

    if isinstance(statement, ast.Assign):
        pending = list(statement.targets)
    elif isinstance(statement, (ast.AugAssign, ast.AnnAssign)):
        pending = [statement.target]
    else:
        return set()

    texts = set()

    while pending:
        target = pending.pop()
        if isinstance(target, (ast.Tuple, ast.List)):
            pending.extend(target.elts)
        elif isinstance(target, ast.Starred):
            pending.append(target.value)
        elif isinstance(target, (ast.Name, ast.Attribute)):
            texts.add(ast.unparse(target))

    return texts


def _header_texts(block: ast.stmt) -> set[str]:
    """Source text of every name or attribute inside a block's header."""

    if isinstance(block, (ast.If, ast.While)):
        header = [block.test]
    elif isinstance(block, (ast.For, ast.AsyncFor)):
        header = [block.iter]
    elif isinstance(block, (ast.With, ast.AsyncWith)):
        header = [item.context_expr for item in block.items]
    elif isinstance(block, ast.Match):
        header = [block.subject]
    else:
        return set()

    return {
        ast.unparse(node)
        for expression in header
        for node in ast.walk(expression)
        if isinstance(node, (ast.Name, ast.Attribute))
    }


def _decide(
    previous: ast.stmt | None,
    current: ast.stmt,
    follows_docstring: bool,
    is_module: bool,
    is_definition_body: bool = False,
) -> _Rule:
    if previous is None and isinstance(current, _DEFINITIONS) and not is_definition_body:
        # ruff format puts a blank line here; forbidding it would undo ruff on every run.
        return _Rule(_Decision.KEEP)

    if previous is None:
        return _Rule(_Decision.FORBID, 'no blank line allowed at start of block')

    if follows_docstring:
        return _Rule(_Decision.REQUIRE, 'blank line needed after docstring')

    if is_module and (isinstance(previous, _DEFINITIONS) or isinstance(current, _DEFINITIONS)):
        return _Rule(_Decision.KEEP)

    if isinstance(previous, _BLOCKS):
        return _Rule(_Decision.REQUIRE, 'blank line needed after block')

    if isinstance(current, _BLOCKS) and _target_texts(previous) & _header_texts(current):
        return _Rule(
            _Decision.FORBID,
            'no blank line allowed between assignment and the block that uses it',
        )

    if isinstance(current, _BLOCKS):
        return _Rule(_Decision.REQUIRE, 'blank line needed before block')

    if isinstance(current, ast.Return):
        return _Rule(_Decision.REQUIRE, 'blank line needed before return')

    if isinstance(current, ast.Raise):
        return _Rule(_Decision.REQUIRE, 'blank line needed before raise')

    return _Rule(_Decision.KEEP)


def _target(rule: _Rule, blank_count: int, is_module: bool) -> tuple[int, str]:
    """The blank-line count `rule` wants for a gap holding `blank_count`, and why."""

    too_many = 'only one blank line allowed inside a function'

    if rule.decision is _Decision.FORBID:
        return 0, rule.message

    if rule.decision is _Decision.REQUIRE and blank_count == 0:
        return 1, rule.message

    if is_module or blank_count <= 1:
        return blank_count, ''

    return 1, too_many


def _plan(source: str) -> tuple[_Lines, list[_Fix]] | None:
    tree = _parse(source)
    if tree is None:
        return None

    lines = _Lines(source)
    planner = _Planner(lines)
    planner.visit_body(tree.body, is_module=True)

    return lines, planner.fixes


def find_spacing_problems(source: str) -> list[tuple[int, str]]:
    plan = _plan(source)
    if plan is None:
        return []

    _, fixes = plan

    return sorted((fix.line, fix.message) for fix in fixes)


def respace(source: str) -> str:
    plan = _plan(source)
    if plan is None:
        return source

    lines, fixes = plan
    fix_by_index = {fix.first_blank_index: fix for fix in fixes}
    newline = lines.newline()
    output = []
    index = 0
    while index < len(lines.text):
        fix = fix_by_index.get(index)
        if fix is None:
            output.append(lines.text[index])
            index += 1
            continue

        output.extend([newline] * fix.target_count)
        output.extend(lines.text[index + fix.blank_count : index + fix.blank_count + 1])
        index += fix.blank_count + 1

    return ''.join(output)


def _read(path: str) -> str | None:
    try:
        with open(path, encoding='utf-8', newline='') as handle:
            return handle.read()
    except UnicodeDecodeError:
        return None


def run(arguments: argparse.Namespace) -> int:
    found_problem = False

    for path in select_files(arguments.paths, ('.py',), os.getcwd()):
        source = _read(path)
        if source is None:
            continue

        if arguments.check:
            for line, message in find_spacing_problems(source):
                print(Problem(path, line, message).render())
                found_problem = True

            continue

        formatted = respace(source)
        if formatted != source:
            with open(path, 'w', encoding='utf-8', newline='') as handle:
                handle.write(formatted)

            print(f'formatted {path}')

    return 1 if found_problem else 0


def register(subparsers) -> None:
    parser = subparsers.add_parser('python-spacing', help='fix blank lines between statements')
    parser.add_argument('--check', action='store_true', help='report problems, write nothing')
    parser.add_argument('paths', nargs='*')
    parser.set_defaults(run=run)
