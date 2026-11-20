#!/usr/bin/env python3
"""Fail when the installed environment differs from the CI pins.

``pip install -c`` constrains only the packages pip decides to install. A new
transitive dependency that is missing from the constraints file still installs
at whatever version PyPI serves that day. Run this right after the install step
of the optional-parser CI job: every installed distribution must be pinned at
exactly the installed version, and every pin must be installed.

Pins come from requirements-ci-parsers.txt plus the exact ``==`` pins in
pyproject.toml for the runtime dependencies and the extras the job installs.
pip, setuptools, wheel and the project itself are ignored.

Exit codes: 0 match, 1 mismatch.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS = "requirements-ci-parsers.txt"
IGNORED = frozenset({"pip", "setuptools", "wheel", "book-to-skill"})


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_constraints(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, separator, version = line.partition("==")
        if not separator or not version.strip():
            raise ValueError(f"{path.name}: not an exact pin: {line}")
        pins[canonical(name.strip())] = version.strip()
    return pins


def _marker_applies(marker: str) -> bool:
    if not marker:
        return True
    from packaging.markers import Marker

    return Marker(marker).evaluate()


def expected_pins(root: Path, extras: list[str]) -> dict[str, str]:
    import tomllib

    pins = read_constraints(root / CONSTRAINTS)
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = list(project.get("dependencies", []))
    for extra in extras:
        requirements.extend(project["optional-dependencies"][extra])
    for requirement in requirements:
        spec, _, marker = requirement.partition(";")
        name, separator, version = spec.partition("==")
        if separator and _marker_applies(marker.strip()):
            pins[canonical(name.strip())] = version.strip()
    return pins


def installed_versions() -> dict[str, str]:
    from importlib import metadata

    return {
        canonical(distribution.metadata["Name"]): distribution.version
        for distribution in metadata.distributions()
    }


def compare(installed: dict[str, str], pins: dict[str, str]) -> list[str]:
    installed = {canonical(name): version for name, version in installed.items()}
    pins = {canonical(name): version for name, version in pins.items()}
    problems = []
    for name in sorted(installed):
        if name in IGNORED:
            continue
        if name not in pins:
            problems.append(f"{name} {installed[name]} is installed but not pinned")
        elif installed[name] != pins[name]:
            problems.append(
                f"{name} is installed at {installed[name]} but pinned at {pins[name]}"
            )
    for name in sorted(pins):
        if name not in installed:
            problems.append(f"{name} is pinned at {pins[name]} but not installed")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--extras", required=True, help="comma-separated extras the job installed"
    )
    args = parser.parse_args(argv)
    problems = compare(installed_versions(), expected_pins(ROOT, args.extras.split(",")))
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(
            f"Update {CONSTRAINTS} so it pins exactly what this job installs.",
            file=sys.stderr,
        )
        return 1
    print(f"Installed packages match {CONSTRAINTS} and the pyproject.toml pins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
