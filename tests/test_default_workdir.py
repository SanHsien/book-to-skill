import os

import pytest

from book_to_skill.config import default_output_dir


def test_default_output_dir_honours_env(monkeypatch, tmp_path):
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(tmp_path / "custom"))
    assert default_output_dir() == tmp_path / "custom"


@pytest.mark.skipif(os.name != "nt", reason="WindowsPath cannot be instantiated on POSIX")
def test_default_output_dir_windows_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("BOOK_SKILL_WORKDIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert default_output_dir() == tmp_path / "Local" / "book-to-skill" / "work"


@pytest.mark.skipif(os.name != "posix", reason="PosixPath cannot be instantiated on Windows")
def test_default_output_dir_posix_uses_shared_temp(monkeypatch, tmp_path):
    monkeypatch.delenv("BOOK_SKILL_WORKDIR", raising=False)
    monkeypatch.setattr(
        "book_to_skill.config.tempfile.gettempdir",
        lambda: str(tmp_path / "tmp"),
    )
    assert default_output_dir() == tmp_path / "tmp" / "book_skill_work"


def test_metadata_records_the_workdir_the_run_used(monkeypatch, tmp_path):
    """Cleanup deletes what this field names, so it must be the resolved path.

    Re-deriving the workdir at cleanup time can name a different directory --
    a concurrent run's, or the previous one if ``BOOK_SKILL_WORKDIR`` changed
    since the extraction -- and ``rmtree`` does not ask twice. Taken from the
    small, additive half of upstream PR #184.
    """
    import json

    from book_to_skill import utils
    from book_to_skill.utils import main

    workdir = tmp_path / "run-workdir"
    source = tmp_path / "sample.md"
    source.write_text(
        "# Chapter 1\n\nSome body text for the extractor.\n", encoding="utf-8"
    )

    monkeypatch.setattr("sys.argv", ["extract.py", str(source), "--install-missing", "no"])
    monkeypatch.setattr(utils, "OUTPUT_DIR", workdir)
    monkeypatch.setattr(utils, "OUTPUT_TEXT", workdir / "full_text.txt")
    monkeypatch.setattr(utils, "OUTPUT_META", workdir / "metadata.json")
    monkeypatch.setattr(utils, "prepare_dependencies", lambda *a: None)

    main()

    metadata = json.loads((workdir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["workdir"] == str(workdir)
    assert metadata["output_text"] == str(workdir / "full_text.txt")
