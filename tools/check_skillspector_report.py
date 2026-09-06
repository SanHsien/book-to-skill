"""Fail closed unless a SkillSpector JSON report accounts for every analyzer."""

from __future__ import annotations

import json
import sys
from pathlib import Path


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
    }
)


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _reference_exceptions_accounted(completeness: dict[str, object]) -> bool:
    exceptions = completeness.get("ledger_exceptions")
    references = completeness.get("references")
    if not isinstance(exceptions, list) or not isinstance(references, list):
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
        or not exceptions
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
            or item.get("reason_code") != "reference_unresolved"
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


def _coverage_accounted(completeness: dict[str, object]) -> bool:
    total = completeness.get("total_components")
    scanned = completeness.get("scanned_components")
    fully = completeness.get("fully_inspected_files")
    partial = completeness.get("partially_inspected_files")
    uninspected = completeness.get("entirely_uninspected_files")
    coverage = completeness.get("coverage_percent")
    limitations = completeness.get("limitations", [])
    return (
        _is_nonnegative_int(total)
        and total > 0
        and scanned == total
        and fully == total
        and partial == 0
        and uninspected == 0
        and isinstance(coverage, (int, float))
        and not isinstance(coverage, bool)
        and coverage == 100.0
        and completeness.get("execution_successful") is True
        and isinstance(limitations, list)
        and not limitations
        and _reference_exceptions_accounted(completeness)
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


def _analyzers_complete(report: dict[str, object]) -> bool:
    completeness = report.get("analysis_completeness")
    if not isinstance(completeness, dict) or not _coverage_accounted(completeness):
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
        elif analyzer_id == "meta_analyzer" and status == "disabled":
            if any(counts) or row.get("reason_code") != "disabled_by_configuration":
                return False
        elif status == "completed":
            allowed_failed = len(binary_exclusions.get(analyzer_id, set()))
            if (
                planned != completed + failed
                or any((partial, skipped, unaccounted))
                or failed != allowed_failed
            ):
                return False
        else:
            return False
    return seen == _EXPECTED_NO_LLM_ANALYZERS


def report_exit_code(report: dict[str, object]) -> int:
    if report.get("execution_successful") is not True:
        return 2
    issues = report.get("issues")
    if not isinstance(issues, list) or not _analyzers_complete(report):
        return 2
    return 1 if issues else 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_skillspector_report.py REPORT.json", file=sys.stderr)
        return 2
    try:
        report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid SkillSpector report: {exc}", file=sys.stderr)
        return 2
    if not isinstance(report, dict):
        print("invalid SkillSpector report: root must be an object", file=sys.stderr)
        return 2
    code = report_exit_code(report)
    if code == 1:
        print(f"SkillSpector report contains {len(report['issues'])} finding(s).", file=sys.stderr)
    elif code == 2:
        print("SkillSpector report is incomplete or has an unaccounted analyzer.", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
