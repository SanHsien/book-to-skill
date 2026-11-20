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


def test_optional_document_parsers_pin_reviewed_security_releases():
    """Untrusted document parsers stay on the reviewed security releases."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for requirement in (
        '"pypdf==6.21.4"',
        '"pdfminer.six==20260107; python_version >= \'3.10\'"',
        '"python-docx==1.2.0"',
        '"docling==2.132.0; python_version >= \'3.10\'"',
    ):
        assert requirement in pyproject
    assert pyproject.count('"pypdf==6.21.4"') == 2
    assert pyproject.count('"docling==2.132.0; python_version >= \'3.10\'"') == 2


_OPTIONAL_PARSER_JOB = "test-optional-parsers"
_CI_CONSTRAINTS = "requirements-ci-parsers.txt"
# The job runs on ubuntu-latest with Python 3.12; dependency markers are judged
# for that platform, not for the machine running this test.
_CI_MARKER_ENVIRONMENT = {
    "extra": "",
    "os_name": "posix",
    "sys_platform": "linux",
    "platform_system": "Linux",
    "platform_machine": "x86_64",
    "platform_python_implementation": "CPython",
    "implementation_name": "cpython",
    "python_version": "3.12",
    "python_full_version": "3.12.0",
}


def _canonical(name: str) -> str:
    import re

    return re.sub(r"[-_.]+", "-", name).lower()


def _ci_constraints() -> dict[str, str]:
    constraints = {}
    for line in (REPO_ROOT / _CI_CONSTRAINTS).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, _, version = line.partition("==")
            assert version.strip(), f"constraint is not an exact pin: {line}"
            constraints[_canonical(name.strip())] = version.strip()
    return constraints


def test_every_pip_install_in_the_optional_parser_job_is_constrained():
    """No pip install in that job may run without the constraints file.

    Checking one known install line is not enough: a second `pip install` step
    added later would install whatever PyPI serves that day.
    """
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    import re

    steps = workflow["jobs"][_OPTIONAL_PARSER_JOB]["steps"]
    # One command per line or per shell separator, so a constrained install
    # cannot cover an unconstrained one in the same step.
    installs = [
        command
        for step in steps
        for command in re.split(r"\n|&&|\|\||;", step.get("run", ""))
        if "pip install" in command
    ]
    assert installs, f"{_OPTIONAL_PARSER_JOB} installs nothing"
    for command in installs:
        assert f"-c {_CI_CONSTRAINTS}" in command, f"unconstrained install: {command}"


def test_optional_parser_ci_job_pins_its_whole_dependency_tree():
    """Every package that job resolves has an exact version.

    That covers the base dependency (defusedxml), each extra the job installs,
    pytest, and their transitive dependencies such as lxml, which parses the
    untrusted HTML and EPUB input. Transitive requirements are read from the
    installed distributions, so they are checked only where those are installed
    (the local .venv with the extras); the direct ones are checked everywhere.
    """
    import re

    tomllib = pytest.importorskip("tomllib")  # stdlib from Python 3.11

    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    groups = re.search(r'-e "\.\[([a-z,]+)\]"', workflow)
    assert groups, f"{_OPTIONAL_PARSER_JOB} must install the extras it tests"
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    constraints = _ci_constraints()

    direct = ["pytest", *project.get("dependencies", [])]
    for group in groups.group(1).split(","):
        direct.extend(project["optional-dependencies"][group])
    pinned_in_pyproject = set()
    pinned_versions = dict(constraints)
    pending = []
    for requirement in direct:
        spec = requirement.split(";", 1)[0].strip()
        name = _canonical(re.split(r"[<>=!~\[ ]", spec, maxsplit=1)[0])
        if "==" in spec:
            pinned_in_pyproject.add(name)
            pinned_versions[name] = spec.split("==", 1)[1].strip()
        else:
            assert name in constraints, f"{spec} is not pinned for CI"
        pending.append(name)

    packaging_requirements = pytest.importorskip("packaging.requirements")
    from importlib import metadata

    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        if distribution.version != pinned_versions.get(name):
            # Another version's requirements say nothing about the pinned one.
            continue
        requires = distribution.requires or []
        for raw in requires:
            requirement = packaging_requirements.Requirement(raw)
            if requirement.marker and not requirement.marker.evaluate(
                _CI_MARKER_ENVIRONMENT
            ):
                continue
            dependency = _canonical(requirement.name)
            assert dependency in constraints or dependency in pinned_in_pyproject, (
                f"{dependency} (required by {name}) is not pinned for CI"
            )
            pending.append(dependency)


def test_fresh_clone_gate_uses_the_pinned_security_scanner():
    requirement = (
        "skillspector @ git+https://github.com/SanHsien/SkillSpector.git@"
        "350e638f316a6fcee8d90f8c3cd296e2d932cda3"
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
        # SC4's evidence comes from a live OSV lookup, so its exact fingerprint
        # changes between runs; pinned to this file and this package name only.
        ("SC4", "requirements-security.txt", "skillspector"),
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

