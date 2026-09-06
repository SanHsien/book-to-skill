"""Regression test: build artifacts must never be tracked in the repository."""

import subprocess
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=30,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"git unavailable: {exc}")


def _tracked_files() -> list[str]:
    """Every path tracked in this repository.

    Uses -z because `git ls-files` otherwise quotes non-ASCII paths
    (`"caf\\303\\251/stale.pyc"`), which would silently defeat the suffix check
    below and let the test pass while bytecode is tracked.
    """
    toplevel = _git("rev-parse", "--show-toplevel")
    if toplevel.returncode != 0:
        pytest.skip("not a git checkout (e.g. installed sdist)")
    if Path(toplevel.stdout.strip()).resolve() != REPO_ROOT:
        # Vendored inside an unrelated repo: `git ls-files` would answer for that
        # repo, so an empty result would be a vacuous pass rather than a real one.
        pytest.skip("REPO_ROOT is not the root of the enclosing git repository")

    listed = _git("ls-files", "-z")
    if listed.returncode != 0:
        pytest.skip("not a git checkout (e.g. installed sdist)")
    return [path for path in listed.stdout.split("\0") if path]


def test_no_compiled_bytecode_is_tracked():
    """`.gitignore` lists *.pyc and __pycache__/, but ignore rules do not untrack
    files already committed. A stale .pyc shipped in the repo is build noise at
    best and a supply-chain smell at worst, since bytecode is not reviewable in a
    diff."""
    offenders = [
        path
        for path in _tracked_files()
        if path.endswith(".pyc") or "__pycache__/" in path
    ]
    assert offenders == [], (
        "compiled bytecode is tracked in git: "
        + ", ".join(offenders)
        + " — untrack the path from git's index"
    )


def test_gitignore_covers_ebooks_and_extractor_output():
    """Local books and extractor dumps must not be easy to `git add` by accident."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("*.pdf", "*.epub", "*.mobi", "/full_text.txt", "/metadata.json"):
        assert pattern in gitignore, f"missing gitignore pattern: {pattern}"

    for rel in ("book.pdf", "full_text.txt"):
        checked = _git("check-ignore", "--no-index", "-q", rel)
        if checked.returncode not in (0, 1):
            pytest.skip(f"git check-ignore failed: {checked.stderr}")
        assert checked.returncode == 0, f"{rel} should be gitignored"


def test_git_checkout_normalizes_text_to_lf():
    """Content-bound scanner baselines must be stable on Windows runners."""
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    rules = {
        line.strip()
        for line in attributes.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "* text=auto eol=lf" in rules

    checked = _git("check-attr", "text", "eol", "--", "tests/test_repo_hygiene.py")
    assert checked.returncode == 0, checked.stderr
    assert "tests/test_repo_hygiene.py: text: auto" in checked.stdout
    assert "tests/test_repo_hygiene.py: eol: lf" in checked.stdout


def test_docx_zipfile_parser_does_not_use_stdlib_etree():
    """R-05: zipfile DOCX path must parse with defusedxml, not xml.etree."""
    source = (REPO_ROOT / "book_to_skill" / "parsers" / "docx.py").read_text(
        encoding="utf-8"
    )
    assert "xml.etree" not in source
    assert "defusedxml.ElementTree" in source


def test_optional_document_parsers_have_security_version_floors():
    """Untrusted documents resolve to reviewed versions, with honest Python markers."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for requirement in (
        '"pypdf==6.17.0"',
        '"pdfminer.six==20260107; python_version >= \'3.10\'"',
        '"python-docx==1.2.0"',
        '"docling==2.126.0; python_version >= \'3.10\'"',
    ):
        assert requirement in pyproject


def test_fresh_clone_gate_uses_the_pinned_security_scanner():
    requirement = (
        "skillspector @ git+https://github.com/SanHsien/SkillSpector.git@"
        "185d610bc1710968f7cce350a0c44098aa88089f"
    )
    assert requirement in (REPO_ROOT / "requirements-security.txt").read_text(
        encoding="utf-8"
    )

    dev_check = (REPO_ROOT / "tools" / "dev_check.ps1").read_text(encoding="utf-8")
    assert "Get-Command skillspector" not in dev_check
    assert "SkillSpectorPython" in dev_check

    for relative_path in ("AGENTS.md", "docs/DEVELOPMENT.md"):
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "requirements-security.txt" in text, relative_path


def test_security_scanner_uses_a_deterministic_python_hash_seed():
    dev_check = (REPO_ROOT / "tools" / "dev_check.ps1").read_text(encoding="utf-8")
    assert '$previousPythonHashSeed = $env:PYTHONHASHSEED' in dev_check
    assert '$env:PYTHONHASHSEED = "0"' in dev_check
    assert '$env:PYTHONHASHSEED = $previousPythonHashSeed' in dev_check


def test_unstable_scanner_findings_use_narrow_suppression_rules():
    baseline = yaml.safe_load(
        (REPO_ROOT / ".skillspector-baseline.yaml").read_text(encoding="utf-8")
    )
    expected = {
        ("PE3", ".gitignore", "*.env*"),
        ("PE3", "tests/test_scan_coverage.py", "*.env*"),
        ("PE3", "tests/test_scan_generated_skill.py", "*.env*"),
        ("PE2", "book_to_skill/dependencies.py", "*sudo*"),
        ("PE2", "README.md", "*sudo*"),
        ("PE2", "README.en.md", "*sudo*"),
        ("RP1", "CONTRIBUTING.md", None),
        ("RP1", "README.en.md", None),
        ("RP1", "README.md", None),
        ("RP1", "SECURITY-NOTICE.md", None),
        ("RP1", "docs/index.md", None),
        ("RP1", "docs/install.md", None),
        ("RP1", "docs/usage.md", None),
        ("AST4", "tests/test_repo_hygiene.py", "*subprocess*"),
    }
    actual = {
        (rule.get("id"), rule.get("path"), rule.get("message"))
        for rule in baseline["rules"]
    }
    assert actual == expected
    assert all(rule.get("reason", "").strip() for rule in baseline["rules"])


def test_publish_instructions_pin_the_npx_skills_cli():
    skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "npx skills@1.5.23 add" in skill
    assert "npx " + "skills add" not in skill

