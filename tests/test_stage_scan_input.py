"""Behaviour tests for tools/stage_scan_input.py.

Each case builds a throwaway git repository, so the tool is exercised against
real ``git ls-files`` output rather than a stub.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "stage_scan_input.py"
_spec = importlib.util.spec_from_file_location("stage_scan_input", TOOL)
stage_scan_input = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stage_scan_input)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    try:
        _git(root, "init", "-q")
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"git unavailable: {exc}")
    _git(root, "config", "user.email", "gate@example.com")
    _git(root, "config", "user.name", "gate")
    _git(root, "config", "core.autocrlf", "false")
    (root / ".gitattributes").write_bytes(
        b"* text=auto eol=lf\n*.bat text eol=crlf\n*.png binary\n"
    )
    (root / ".gitignore").write_bytes(b"out/\n")
    (root / "skills" / "demo").mkdir(parents=True)
    (root / "skills" / "demo" / "SKILL.md").write_bytes(b"line one\nline two\n")
    (root / "run.bat").write_bytes(b"@echo off\r\necho hi\r\n")
    (root / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\r\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_crlf_left_by_an_old_checkout_is_staged_as_lf(repo, tmp_path):
    # The index holds LF; a checkout made before .gitattributes kept CRLF.
    (repo / "skills" / "demo" / "SKILL.md").write_bytes(b"line one\r\nline two\r\n")
    dest = tmp_path / "stage"
    _, normalized = stage_scan_input.stage(repo, dest)
    assert (dest / "skills" / "demo" / "SKILL.md").read_bytes() == b"line one\nline two\n"
    assert normalized == 1


def test_binary_files_are_copied_byte_for_byte(repo, tmp_path):
    dest = tmp_path / "stage"
    stage_scan_input.stage(repo, dest)
    assert (dest / "icon.png").read_bytes() == b"\x89PNG\r\n\x1a\n\x00\r\n"


def test_files_whose_attributes_ask_for_crlf_keep_it(repo, tmp_path):
    dest = tmp_path / "stage"
    stage_scan_input.stage(repo, dest)
    assert (dest / "run.bat").read_bytes() == b"@echo off\r\necho hi\r\n"


def test_untracked_files_are_staged_unchanged_and_ignored_files_are_not(repo, tmp_path):
    (repo / "notes.txt").write_bytes(b"draft\r\n")
    (repo / "out").mkdir()
    (repo / "out" / "book.txt").write_bytes(b"generated\n")
    dest = tmp_path / "stage"
    stage_scan_input.stage(repo, dest)
    assert (dest / "notes.txt").read_bytes() == b"draft\r\n"
    assert not (dest / "out").exists()


def test_pathspec_and_exclude_limit_what_is_staged(repo, tmp_path):
    only_skills = tmp_path / "skills-only"
    stage_scan_input.stage(repo, only_skills, ["skills"])
    assert (only_skills / "skills" / "demo" / "SKILL.md").is_file()
    assert not (only_skills / "run.bat").exists()
    without_bat = tmp_path / "without-bat"
    stage_scan_input.stage(repo, without_bat, exclude=["run.bat"])
    assert not (without_bat / "run.bat").exists()
    assert (without_bat / "icon.png").is_file()


def test_command_line_reports_counts(repo, tmp_path, capsys):
    (repo / "skills" / "demo" / "SKILL.md").write_bytes(b"a\r\n")
    assert stage_scan_input.main(["--repo", str(repo), "--dest", str(tmp_path / "s")]) == 0
    assert "1 CRLF text file(s) normalized to LF" in capsys.readouterr().out
