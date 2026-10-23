"""Fail closed unless a SkillSpector JSON report accounts for every analyzer."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

_WORK_COUNTERS = ("planned_work", "completed", "partial", "skipped", "failed", "unaccounted")
_EXPECTED_NO_LLM_ANALYZERS = frozenset(
    {
        "artifact_integrity",
        "behavioral_ast",
        "behavioral_taint_tracking",
        "bundled_execution_surface",
        "mcp_least_privilege",
        "mcp_rug_pull",
        "mcp_tool_poisoning",
        "meta_analyzer",
        "static_patterns_agent_snooping",
        "static_patterns_anti_refusal",
        "static_patterns_data_exfiltration",
        "static_patterns_deserialization",
        "static_patterns_excessive_agency",
        "static_patterns_harmful_content",
        "static_patterns_memory_poisoning",
        "static_patterns_output_handling",
        "static_patterns_privilege_escalation",
        "static_patterns_prompt_injection",
        "static_patterns_rogue_agent",
        "static_patterns_ssrf",
        "static_patterns_supply_chain",
        "static_patterns_system_prompt_leakage",
        "static_patterns_tool_misuse",
        "static_yara",
        "semantic_developer_intent",
        "semantic_quality_policy",
        "semantic_security_discovery",
    }
)
# Analyzers a --no-llm scan must report as switched off by configuration, never as run.
# The semantic analyzers need an LLM; since the 2026-09-17 scanner sync the report lists
# them explicitly instead of omitting them, so their absence or any work is a contract break.
_DISABLED_WITHOUT_LLM = frozenset(
    {
        "meta_analyzer",
        "semantic_developer_intent",
        "semantic_quality_policy",
        "semantic_security_discovery",
    }
)


# Non-fatal reference outcomes. SkillSpector 2.12.0 split the old single reason into
# reference_missing (no bundled artifact matches, e.g. a file the skill writes at run
# time) and reference_unresolved (several artifacts match); both leave the reference
# partial without failing the scan.
_NONFATAL_REFERENCE_REASONS = frozenset({"reference_missing", "reference_unresolved"})


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _reference_exceptions_accounted(
    completeness: dict[str, object], exceptions: list[object], *, has_static_partials: bool
) -> bool:
    references = completeness.get("references")
    if not isinstance(references, list):
        return False
    if completeness.get("status") == "complete":
        return (
            completeness.get("is_complete") is True
            and not exceptions
            and all(
                isinstance(item, dict) and item.get("disposition") != "partial"
                for item in references
            )
        )
    if (
        completeness.get("status") != "partial"
        or completeness.get("is_complete") is not False
        or not (exceptions or has_static_partials)
    ):
        return False

    exception_keys: set[tuple[str, int]] = set()
    for item in exceptions:
        if not isinstance(item, dict):
            return False
        path = item.get("path")
        start_line = item.get("start_line")
        end_line = item.get("end_line")
        if (
            item.get("outcome") != "partial"
            or item.get("phase") != "reference_resolution"
            or item.get("reason_code") not in _NONFATAL_REFERENCE_REASONS
            or item.get("fatal") is not False
            or not isinstance(path, str)
            or not path
            or not _is_nonnegative_int(start_line)
            or not _is_nonnegative_int(end_line)
            or end_line < start_line
        ):
            return False
        exception_keys.add((path, start_line))

    reference_keys: set[tuple[str, int]] = set()
    for item in references:
        if not isinstance(item, dict):
            return False
        if item.get("disposition") != "partial":
            continue
        path = item.get("source_path")
        line = item.get("line")
        if (
            item.get("status") != "missing"
            or item.get("target_path") is not None
            or not isinstance(path, str)
            or not path
            or not _is_nonnegative_int(line)
        ):
            return False
        reference_keys.add((path, line))
    return exception_keys == reference_keys


def _static_partials(
    completeness: dict[str, object], reviewed: frozenset[tuple[str, str, str]]
) -> tuple[list[object], set[str], dict[str, int]] | None:
    """Split reviewed static parse limits out of the ledger exceptions.

    Returns the remaining exceptions, the partially inspected paths and, per analyzer,
    how many partial units the reviewed exceptions explain. A static exception that no
    reviewed partial covers makes the scan incomplete (None).
    """
    exceptions = completeness.get("ledger_exceptions")
    if not isinstance(exceptions, list):
        return None
    remaining: list[object] = []
    paths: set[str] = set()
    per_analyzer: dict[str, int] = {}
    for item in exceptions:
        if not isinstance(item, dict) or item.get("phase") != "static":
            remaining.append(item)
            continue
        path = item.get("path")
        reason = item.get("reason_code")
        analyzers = item.get("analyzers")
        if (
            item.get("outcome") != "partial"
            or item.get("fatal") is not False
            or not isinstance(path, str)
            or not isinstance(reason, str)
            or not isinstance(analyzers, list)
            or not analyzers
        ):
            return None
        for analyzer in analyzers:
            if (path, analyzer, reason) not in reviewed:
                return None
            per_analyzer[analyzer] = per_analyzer.get(analyzer, 0) + 1
        paths.add(path)
    return remaining, paths, per_analyzer


def _coverage_accounted(
    completeness: dict[str, object],
    remaining: list[object],
    partial_paths: set[str],
    degraded: set[str],
) -> bool:
    total = completeness.get("total_components")
    scanned = completeness.get("scanned_components")
    fully = completeness.get("fully_inspected_files")
    partial = completeness.get("partially_inspected_files")
    uninspected = completeness.get("entirely_uninspected_files")
    coverage = completeness.get("coverage_percent")
    limitations = completeness.get("limitations", [])
    if not _is_nonnegative_int(total) or total <= 0:
        return False
    expected_scanned = total - len(partial_paths)
    expected_limitations = sorted(f"Analyzer {name} status: degraded." for name in degraded)
    return (
        scanned == expected_scanned
        and fully == expected_scanned
        and partial == len(partial_paths)
        and uninspected == 0
        and isinstance(coverage, (int, float))
        and not isinstance(coverage, bool)
        and abs(coverage - 100.0 * expected_scanned / total) < 0.1
        and completeness.get("execution_successful") is True
        and isinstance(limitations, list)
        and sorted(limitations) == expected_limitations
        and _reference_exceptions_accounted(
            completeness, remaining, has_static_partials=bool(partial_paths)
        )
    )


def _binary_scope_exclusions(completeness: dict[str, object]) -> dict[str, set[str]] | None:
    exclusions = completeness.get("scope_exclusions", [])
    if not isinstance(exclusions, list):
        return None
    accounted: dict[str, set[str]] = {}
    for item in exclusions:
        if not isinstance(item, dict):
            return None
        if item.get("outcome") != "out_of_scope" or item.get("reason_code") != "binary_content":
            continue
        path = item.get("path")
        analyzers = item.get("analyzers")
        if not isinstance(path, str) or not path or not isinstance(analyzers, list):
            return None
        if any(not isinstance(analyzer, str) or not analyzer for analyzer in analyzers):
            return None
        for analyzer in analyzers:
            accounted.setdefault(analyzer, set()).add(path)
    return accounted


def _analyzers_complete(
    report: dict[str, object], reviewed: frozenset[tuple[str, str, str]] = frozenset()
) -> bool:
    completeness = report.get("analysis_completeness")
    if not isinstance(completeness, dict):
        return False
    split = _static_partials(completeness, reviewed)
    if split is None:
        return False
    remaining, partial_paths, partial_by_analyzer = split
    if not _coverage_accounted(completeness, remaining, partial_paths, set(partial_by_analyzer)):
        return False
    statuses = completeness.get("analyzer_statuses")
    if not isinstance(statuses, list) or not statuses:
        return False
    binary_exclusions = _binary_scope_exclusions(completeness)
    if binary_exclusions is None:
        return False

    seen: set[str] = set()
    for row in statuses:
        if not isinstance(row, dict):
            return False
        analyzer_id = row.get("analyzer_id")
        if not isinstance(analyzer_id, str) or not analyzer_id or analyzer_id in seen:
            return False
        seen.add(analyzer_id)
        counts = [row.get(name) for name in _WORK_COUNTERS]
        if any(not _is_nonnegative_int(value) for value in counts):
            return False
        planned, completed, partial, skipped, failed, unaccounted = counts
        status = row.get("status")
        if status == "not_applicable":
            if any(counts):
                return False
        elif analyzer_id in _DISABLED_WITHOUT_LLM and status == "disabled":
            if any(counts) or row.get("reason_code") != "disabled_by_configuration":
                return False
        elif analyzer_id.startswith("semantic_"):
            # An LLM analyzer doing work in a --no-llm scan means the gate is not
            # measuring what it claims to measure.
            return False
        elif status == "completed" and analyzer_id not in partial_by_analyzer:
            # Out-of-scope binaries count as failed work before SkillSpector 2.12.0 and as
            # completed (failed == 0) from 2.12.0 on; either matches an explicit exclusion.
            allowed_failed = len(binary_exclusions.get(analyzer_id, set()))
            if (
                planned != completed + failed
                or any((partial, skipped, unaccounted))
                or failed not in {0, allowed_failed}
            ):
                return False
        elif status == "degraded" and analyzer_id in partial_by_analyzer:
            # Degraded only by reviewed static parse limits: every partial unit must be
            # one of them, and nothing may be skipped or unaccounted.
            allowed_failed = len(binary_exclusions.get(analyzer_id, set()))
            if (
                planned != completed + partial + failed
                or partial != partial_by_analyzer[analyzer_id]
                or any((skipped, unaccounted))
                or failed not in {0, allowed_failed}
            ):
                return False
        else:
            return False
    expected = set(_EXPECTED_NO_LLM_ANALYZERS)
    if partial_paths and "reference_coverage" in seen:
        # The scanner adds this row (with an AE1 finding per reference) only when a
        # referenced file was not fully inspected -- here, a reviewed partial.
        expected.add("reference_coverage")
    return seen == expected


def reviewed_partials(baseline: dict[str, object], scan_root: Path) -> frozenset[tuple[str, str, str]]:
    """Reviewed static parse limits whose file is unchanged since review.

    The whole repository is scanned as one bundle, so entries carry no skill scope;
    each is pinned to the SHA-256 of the file as staged (LF) under ``scan_root``.
    """
    entries = baseline.get("reviewed_partials") or []
    if not isinstance(entries, list):
        raise ValueError("reviewed_partials must be a list")
    keys = ("path", "reason_code", "sha256", "reason")
    reviewed: set[tuple[str, str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each reviewed partial must be a mapping")
        fields = {key: entry.get(key) for key in keys}
        if any(not isinstance(value, str) or not value.strip() for value in fields.values()):
            raise ValueError("a reviewed partial needs " + ", ".join(keys))
        # One limit can degrade several analyzers on the same file; list them all.
        analyzers = entry.get("analyzers")
        if analyzers is None and isinstance(entry.get("analyzer"), str):
            analyzers = [entry["analyzer"]]
        if (
            not isinstance(analyzers, list)
            or not analyzers
            or any(not isinstance(name, str) or not name.strip() for name in analyzers)
        ):
            raise ValueError("a reviewed partial needs analyzer or a non-empty analyzers list")
        target = scan_root / fields["path"]
        if not target.is_file():
            continue
        if hashlib.sha256(target.read_bytes()).hexdigest() != fields["sha256"]:
            continue
        for name in analyzers:
            reviewed.add((fields["path"], name, fields["reason_code"]))
    return frozenset(reviewed)


def report_exit_code(
    report: dict[str, object], reviewed: frozenset[tuple[str, str, str]] = frozenset()
) -> int:
    if report.get("execution_successful") is not True:
        return 2
    issues = report.get("issues")
    if not isinstance(issues, list) or not _analyzers_complete(report, reviewed):
        return 2
    return 1 if issues else 0


def main() -> int:
    args = sys.argv[1:]
    if len(args) not in (1, 3):
        print("usage: check_skillspector_report.py REPORT.json [BASELINE.yaml SCAN_ROOT]", file=sys.stderr)
        return 2
    try:
        report = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid SkillSpector report: {exc}", file=sys.stderr)
        return 2
    reviewed: frozenset[tuple[str, str, str]] = frozenset()
    if len(args) == 3:
        try:
            baseline = yaml.safe_load(Path(args[1]).read_text(encoding="utf-8")) or {}
            reviewed = reviewed_partials(baseline, Path(args[2]))
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"invalid reviewed_partials: {exc}", file=sys.stderr)
            return 2
    if not isinstance(report, dict):
        print("invalid SkillSpector report: root must be an object", file=sys.stderr)
        return 2
    code = report_exit_code(report, reviewed)
    if code == 1:
        print(f"SkillSpector report contains {len(report['issues'])} finding(s).", file=sys.stderr)
    elif code == 2:
        print("SkillSpector report is incomplete or has an unaccounted analyzer.", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
