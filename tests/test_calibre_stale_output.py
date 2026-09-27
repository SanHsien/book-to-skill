"""Regression tests: the Calibre path must not reuse an earlier source's output.

`extract_with_ebook_convert()` treats "exit code 0 and the output file exists"
as success. The work directory is per-process and shared by every source in one
batch, so when a conversion reports success without writing anything, a file
left by an earlier source in the same run satisfies that check: one book's text
is returned for another source and recorded under *its* name in metadata.json.
Nothing downstream can tell, which is the same failure mode as the shared
work-directory bug (see test_per_run_workdir.py).

The fix gives each call its own output filename, so "the file exists" can only
be true for a file this call wrote.

No Calibre install is required — `shutil.which` and `subprocess.run` are patched.
"""

import importlib
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

BOOK_A_TEXT = "TEXT OF BOOK A\n"


@pytest.fixture
def calibre_module(monkeypatch, tmp_path):
    """Import the parser against an isolated work directory.

    config reads BOOK_SKILL_WORKDIR at import time, so it is imported after the
    env var is set — and reloaded so a previously imported config cannot leave
    the real temp work directory in place.
    """
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(tmp_path))
    import book_to_skill.config as config

    importlib.reload(config)
    import book_to_skill.parsers.calibre as calibre

    importlib.reload(calibre)
    yield calibre, tmp_path
    # Leave the module-level OUTPUT_DIR pointing somewhere harmless for later tests.
    monkeypatch.delenv("BOOK_SKILL_WORKDIR", raising=False)
    importlib.reload(config)
    importlib.reload(calibre)


def _convert_without_writing(calibre, source_name="bookB.mobi"):
    """Model ebook-convert reporting success while writing nothing."""
    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", return_value=mock.Mock(returncode=0)):
        return calibre.extract_with_ebook_convert(source_name)


def test_output_name_is_unique_per_call(calibre_module):
    """Two conversions must not share one output file."""
    calibre, workdir = calibre_module
    seen = []

    def record_output_path(argv, **_kwargs):
        seen.append(Path(argv[2]))
        Path(argv[2]).write_text(f"text {len(seen)}\n", encoding="utf-8")
        return mock.Mock(returncode=0)

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", side_effect=record_output_path):
        first = calibre.extract_with_ebook_convert("bookA.mobi")
        second = calibre.extract_with_ebook_convert("bookB.mobi")

    assert first == "text 1\n"
    assert second == "text 2\n", "the second conversion read the first one's file"
    assert seen[0] != seen[1]
    assert seen[0].parent == workdir and seen[1].parent == workdir


def test_success_without_output_does_not_reuse_an_earlier_result(calibre_module):
    """A previous source's output must not satisfy a later, empty conversion."""
    calibre, workdir = calibre_module

    def run_writes_output(argv, **_kwargs):
        Path(argv[2]).write_text(BOOK_A_TEXT, encoding="utf-8")
        return mock.Mock(returncode=0)

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", side_effect=run_writes_output):
        text_a = calibre.extract_with_ebook_convert("bookA.mobi")
    assert text_a == BOOK_A_TEXT

    # Same run, next source: success reported, nothing written.
    assert _convert_without_writing(calibre) is None

    # And the earlier artifact is still readable on its own terms.
    leftovers = [p for p in workdir.iterdir() if p.is_file()]
    assert leftovers, "the first conversion's output should still exist"


def test_success_with_existing_output_still_returns_text(calibre_module):
    """The guard must still accept a conversion that genuinely writes output."""
    calibre, _workdir = calibre_module

    def run_writes_output(argv, **_kwargs):
        Path(argv[2]).write_text("FRESH BODY\n", encoding="utf-8")
        return mock.Mock(returncode=0)

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", side_effect=run_writes_output):
        assert calibre.extract_with_ebook_convert("book.mobi") == "FRESH BODY\n"


def test_nonzero_exit_returns_none(calibre_module):
    """A failed conversion stays a failure, whether or not a file exists."""
    calibre, workdir = calibre_module
    (workdir / "leftover.txt").write_text("STALE\n", encoding="utf-8")

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", return_value=mock.Mock(returncode=1)):
        assert calibre.extract_with_ebook_convert("book.mobi") is None


def test_missing_ebook_convert_returns_none(calibre_module):
    """No Calibre on PATH is a skip, not an error."""
    calibre, _workdir = calibre_module

    with mock.patch.object(calibre.shutil, "which", return_value=None):
        assert calibre.extract_with_ebook_convert("book.mobi") is None
