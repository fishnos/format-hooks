import subprocess

from format_hooks.file_selection import select_files
from format_hooks.problems import Problem


def test_untracked_files_are_selected_when_no_paths_are_given(tmp_path):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / '.gitignore').write_text('ignored.py\n')
    (tmp_path / 'new.py').write_text('')
    (tmp_path / 'ignored.py').write_text('')

    selected = select_files([], ('.py',), str(tmp_path))

    assert selected == [str(tmp_path / 'new.py')]


def test_given_paths_are_filtered_by_suffix(tmp_path):
    selected = select_files(['a.py', 'b.sh'], ('.py',), str(tmp_path))

    assert selected == ['a.py']


def test_problem_with_a_line_renders_path_line_and_message():
    problem = Problem('check.py', 57, 'blank line needed before return')

    assert problem.render() == 'check.py:57: blank line needed before return'


def test_problem_without_a_line_renders_path_and_message():
    problem = Problem('check.py', None, '24% comment lines, limit 20%')

    assert problem.render() == 'check.py: 24% comment lines, limit 20%'
