import os

import pytest

from book_to_skill.config import default_output_dir


def test_default_output_dir_honours_env(monkeypatch, tmp_path):
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(tmp_path / "custom"))
    assert default_output_dir() == tmp_path / "custom"


def test_default_output_dir_windows_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", "")
    monkeypatch.delenv("BOOK_SKILL_WORKDIR", raising=False)
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert default_output_dir() == tmp_path / "Local" / "book-to-skill" / "work"


@pytest.mark.skipif(os.name != "posix", reason="PosixPath cannot be instantiated on Windows")
def test_default_output_dir_posix_uses_shared_temp(monkeypatch, tmp_path):
    monkeypatch.delenv("BOOK_SKILL_WORKDIR", raising=False)
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(
        "book_to_skill.config.tempfile.gettempdir",
        lambda: str(tmp_path / "tmp"),
    )
    assert default_output_dir() == tmp_path / "tmp" / "book_skill_work"
