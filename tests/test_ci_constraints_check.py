"""The optional-parser CI job verifies that what it installed is exactly what is pinned.

Pinning with ``pip install -c`` only constrains packages pip decides to install.
A new transitive dependency that nobody added to the constraints file is still
installed at whatever version PyPI serves that day, and nothing would notice.
tools/check_ci_constraints.py compares the installed environment with the pins
and fails on anything unpinned or different.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_ci_constraints", ROOT / "tools" / "check_ci_constraints.py"
)
assert _spec is not None and _spec.loader is not None
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


PINS = {"lxml": "6.1.3", "pytest": "9.2.0"}


def test_matching_environment_passes():
    installed = {"lxml": "6.1.3", "pytest": "9.2.0"}
    assert checker.compare(installed, PINS) == []


def test_unpinned_package_fails():
    installed = {"lxml": "6.1.3", "pytest": "9.2.0", "six": "1.17.0"}
    assert checker.compare(installed, PINS) == ["six 1.17.0 is installed but not pinned"]


def test_version_mismatch_fails():
    installed = {"lxml": "6.2.0", "pytest": "9.2.0"}
    assert checker.compare(installed, PINS) == [
        "lxml is installed at 6.2.0 but pinned at 6.1.3"
    ]


def test_pinned_but_missing_package_fails():
    # A pin nothing installs any more is stale: the file no longer describes the job.
    installed = {"pytest": "9.2.0"}
    assert checker.compare(installed, PINS) == ["lxml is pinned at 6.1.3 but not installed"]


def test_installer_and_project_are_ignored():
    installed = {
        "lxml": "6.1.3",
        "pytest": "9.2.0",
        "pip": "26.0",
        "setuptools": "80.0",
        "wheel": "0.46",
        "book-to-skill": "1.4.0",
    }
    assert checker.compare(installed, PINS) == []


def test_names_are_compared_in_canonical_form():
    installed = {"Typing_Extensions": "4.16.0"}
    assert checker.compare(installed, {"typing-extensions": "4.16.0"}) == []


def test_expected_pins_combine_constraints_and_exact_pyproject_pins():
    import pytest

    pytest.importorskip("tomllib")  # stdlib from Python 3.11
    pytest.importorskip("packaging")
    pins =checker.expected_pins(ROOT, ["html", "epub", "docx", "pdf", "rtf"])
    assert pins["lxml"] == "6.1.3"          # requirements-ci-parsers.txt
    assert pins["pypdf"] == "6.21.4"        # pyproject.toml exact pin
    assert pins["python-docx"] == "1.2.0"
    assert "trafilatura" in pins and "defusedxml" in pins
    # Only the extras the job installs: the technical extra is not installed.
    assert "docling" not in pins


def test_ci_job_runs_the_check_after_installing():
    import yaml

    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    runs = [step.get("run", "") for step in workflow["jobs"]["test-optional-parsers"]["steps"]]
    install = next(i for i, run in enumerate(runs) if "pip install" in run)
    check = next(
        (i for i, run in enumerate(runs) if "tools/check_ci_constraints.py" in run), None
    )
    assert check is not None, "the job must verify its installed packages"
    assert check > install
