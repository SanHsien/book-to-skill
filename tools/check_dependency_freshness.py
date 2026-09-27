#!/usr/bin/env python3
"""Check declared direct dependencies against the latest PyPI releases."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parent.parent

_REQUIREMENT_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*(.*)$")
_MINIMUM_RE = re.compile(
    r"(>=|>|==|~=)\s*([0-9][0-9A-Za-z.!+_-]*(?:\.[0-9A-Za-z!+_-]+)*)"
)


def normalize_package_name(package_name: str) -> str:
    return re.sub(r"[-_.]+", "-", package_name).lower()


def is_newer_version(latest: str, current: str) -> bool:
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False


HOLD_MARKER = "freshness-hold:"
DEFERRALS_PATH = ROOT / ".github" / "dependency-deferrals.json"


def parse_holds(text: str) -> dict[str, str]:
    """Map package -> reason for ``# freshness-hold:`` comments in the source file.

    A hold is a standing policy, not a postponement: some floors are the floor we
    want, and re-asking every month turns the report into noise. TOML parsers drop
    comments, so the marker is read off the raw text of the declaring line.
    """
    holds: dict[str, str] = {}
    for line in text.splitlines():
        head, marker, comment = line.partition("#")
        reason = comment.strip()[len(HOLD_MARKER) :].strip()
        if not marker or not comment.strip().startswith(HOLD_MARKER) or not reason:
            continue
        for quoted in re.findall(r"\"([^\"]+)\"|'([^']+)'", head):
            match = _REQUIREMENT_RE.match(quoted[0] or quoted[1])
            if match:
                holds[match.group(1).lower()] = reason
    return holds


def load_deferrals(path: Path = DEFERRALS_PATH) -> dict[str, tuple[str, str]]:
    """Read reviewed-but-not-now decisions: package -> (reviewed release, reason).

    The reviewed release is what makes a deferral expire by itself: once PyPI moves
    past it the report asks again, so a deferral cannot quietly become a silenced
    check. An entry without it is ignored for exactly that reason.
    """
    try:
        entries = json.loads(path.read_text(encoding="utf-8")).get("deferrals", {})
    except (OSError, ValueError):
        return {}
    deferrals: dict[str, tuple[str, str]] = {}
    for name, entry in (entries or {}).items():
        if not isinstance(entry, dict):
            continue
        latest = str(entry.get("deferredLatest", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        if latest and reason:
            deferrals[name.lower()] = (latest, reason)
    return deferrals


def needs_review(row: dict) -> bool:
    """An aged floor still counts unless a hold or a live deferral covers it."""
    return bool(row["outdated"]) and not row.get("hold") and not row.get("deferred_reason")


def _parse_requirements(
    requirements: Iterable[str],
    group: str,
) -> list[dict[str, str]]:
    packages = []
    seen: set[str] = set()
    for requirement in requirements:
        match = _REQUIREMENT_RE.match(requirement)
        if not match:
            continue
        name, specifiers = match.groups()
        key = normalize_package_name(name)
        if key in seen:
            continue
        seen.add(key)
        minimum_match = _MINIMUM_RE.search(specifiers)
        packages.append(
            {
                "name": name,
                "minimum": minimum_match.group(2) if minimum_match else "",
                "requirement": requirement,
                "group": group,
            }
        )
    return packages


def load_direct_dependencies(
    pyproject_path: Path = ROOT / "pyproject.toml",
) -> list[dict[str, str]]:
    # tomllib arrived in 3.11 and the test matrix still covers 3.9/3.10, so the
    # import stays inside the one function that needs it. Everything else here --
    # the version comparison, the hold marker, the deferrals -- is plain stdlib,
    # and a maintenance tool that cannot even be imported on a supported Python
    # takes its unit tests down with it.
    import tomllib

    with pyproject_path.open("rb") as file:
        data = tomllib.load(file)
    holds = parse_holds(pyproject_path.read_text(encoding="utf-8"))

    project = data.get("project", {})
    packages = _parse_requirements(project.get("dependencies", []), "runtime")
    for group, requirements in project.get("optional-dependencies", {}).items():
        if group == "all":
            continue
        packages.extend(_parse_requirements(requirements, f"optional:{group}"))
    packages.extend(
        _parse_requirements(
            data.get("build-system", {}).get("requires", []),
            "build-system",
        )
    )
    for package in packages:
        package["hold"] = holds.get(package["name"].lower(), "")
    return packages


def fetch_pypi_version(package_name: str, timeout: float = 10.0) -> str | None:
    quoted_name = urllib.parse.quote(package_name, safe="")
    request = urllib.request.Request(
        f"https://pypi.org/pypi/{quoted_name}/json",
        headers={
            "Accept": "application/json",
            "User-Agent": "book-to-skill-dependency-check",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
        return data.get("info", {}).get("version")
    except (OSError, ValueError):
        return None


def collect_status(
    packages: Iterable[dict[str, str]],
    deferrals: dict[str, tuple[str, str]] | None = None,
) -> list[dict[str, object]]:
    deferrals = deferrals if deferrals is not None else load_deferrals()
    rows = []
    for package in packages:
        minimum = package["minimum"]
        latest = fetch_pypi_version(package["name"])
        fetch_failed = latest is None
        outdated = bool(
            minimum and latest and is_newer_version(str(latest), minimum)
        )
        reviewed, reason = deferrals.get(package["name"].lower(), ("", ""))
        deferred = bool(reviewed and latest and not is_newer_version(str(latest), reviewed))

        rows.append(
            {
                **package,
                "latest": latest or "unknown",
                "hold": package.get("hold", ""),
                "deferred_reason": reason if deferred else "",
                "outdated": outdated,
                "check_failed": fetch_failed,
            }
        )
    return rows


def render_markdown(rows: list[dict[str, object]]) -> str:
    lines = [
        "# book-to-skill dependency freshness",
        "",
        "| Package | Group | Declared | PyPI latest | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row["check_failed"]:
            status = "CHECK FAILED"
        elif row["outdated"] and row.get("hold"):
            status = f"HELD: {row['hold']}"
        elif row["outdated"] and row.get("deferred_reason"):
            status = f"DEFERRED at {row['latest']}: {row['deferred_reason']}"
        elif row["outdated"]:
            status = "REVIEW UPDATE"
        elif not row["minimum"]:
            status = "UNPINNED"
        else:
            status = "OK"
        lines.append(
            f"| `{row['name']}` | `{row['group']}` | "
            f"`{row['requirement']}` | `{row['latest']}` | {status} |"
        )
    lines.extend(
        [
            "",
            "This report compares repository declarations with PyPI. "
            "It does not inspect installed packages.",
            "Unpinned extras are informational; pinned outdated versions "
            "and fetch failures require review.",
            "Dependency pull requests are never merged automatically.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_github_output(
    outdated: bool,
    check_failed: bool,
    report_path: Path,
) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"outdated={'true' if outdated else 'false'}\n")
        output.write(f"check_failed={'true' if check_failed else 'false'}\n")
        output.write(
            f"needs_attention={'true' if outdated or check_failed else 'false'}\n"
        )
        output.write(f"report_path={report_path.as_posix()}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check book-to-skill direct dependencies against PyPI"
    )
    parser.add_argument(
        "--output",
        default="dependency-freshness-report.md",
        help="Markdown report output path",
    )
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="Write status fields to GITHUB_OUTPUT",
    )
    args = parser.parse_args()

    rows = collect_status(load_direct_dependencies())
    report = render_markdown(rows)
    output_path = Path(args.output)
    output_path.write_text(report, encoding="utf-8")
    print(report)

    outdated = any(needs_review(row) for row in rows)
    check_failed = not rows or any(bool(row["check_failed"]) for row in rows)
    if args.github_output:
        write_github_output(outdated, check_failed, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
