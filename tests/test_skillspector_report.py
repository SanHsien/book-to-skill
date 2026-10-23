import hashlib

import pytest

from tools.check_skillspector_report import report_exit_code, reviewed_partials


EXPECTED_ANALYZERS = {
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
DISABLED_WITHOUT_LLM = {
    "meta_analyzer",
    "semantic_developer_intent",
    "semantic_quality_policy",
    "semantic_security_discovery",
}


def _completed_analyzer(analyzer_id):
    return {
        "analyzer_id": analyzer_id,
        "status": "completed",
        "planned_work": 1,
        "completed": 1,
        "partial": 0,
        "skipped": 0,
        "failed": 0,
        "unaccounted": 0,
    }


def _complete_report(*, issues=None):
    statuses = [_completed_analyzer(item) for item in sorted(EXPECTED_ANALYZERS)]
    for item in statuses:
        if item["analyzer_id"] in DISABLED_WITHOUT_LLM:
            item.update(
                status="disabled",
                planned_work=0,
                completed=0,
                reason_code="disabled_by_configuration",
            )
    return {
        "execution_successful": True,
        "issues": [] if issues is None else issues,
        "analysis_completeness": {
            "total_components": 1,
            "scanned_components": 1,
            "coverage_percent": 100.0,
            "is_complete": True,
            "status": "complete",
            "execution_successful": True,
            "fully_inspected_files": 1,
            "partially_inspected_files": 0,
            "entirely_uninspected_files": 0,
            "ledger_exceptions": [],
            "scope_exclusions": [],
            "analyzer_statuses": statuses,
            "references": [],
        },
    }


def test_report_exit_code_accepts_complete_no_llm_scan():
    assert report_exit_code(_complete_report()) == 0


def test_report_exit_code_distinguishes_findings():
    assert report_exit_code(_complete_report(issues=[{}])) == 1


def test_report_exit_code_rejects_degraded_analyzer():
    report = _complete_report()
    report["analysis_completeness"]["analyzer_statuses"][-2].update(
        status="degraded", completed=2, partial=1
    )
    assert report_exit_code(report) == 2


def test_report_exit_code_rejects_unknown_disabled_analyzer():
    report = _complete_report()
    report["analysis_completeness"]["analyzer_statuses"][-2].update(
        status="disabled", planned_work=0, completed=0
    )
    assert report_exit_code(report) == 2


def test_report_exit_code_rejects_semantic_analyzer_that_ran_without_llm():
    report = _complete_report()
    row = next(
        item
        for item in report["analysis_completeness"]["analyzer_statuses"]
        if item["analyzer_id"] == "semantic_security_discovery"
    )
    row.update(status="completed", planned_work=1, completed=1)
    row.pop("reason_code")
    assert report_exit_code(report) == 2


def test_report_exit_code_rejects_missing_semantic_analyzer_row():
    report = _complete_report()
    statuses = report["analysis_completeness"]["analyzer_statuses"]
    report["analysis_completeness"]["analyzer_statuses"] = [
        item for item in statuses if item["analyzer_id"] != "semantic_quality_policy"
    ]
    assert report_exit_code(report) == 2


def test_report_exit_code_rejects_missing_expected_analyzer():
    report = _complete_report()
    report["analysis_completeness"]["analyzer_statuses"].pop()
    assert report_exit_code(report) == 2


def test_report_exit_code_rejects_unaccounted_partial_completeness():
    report = _complete_report()
    report["analysis_completeness"].update(status="partial", is_complete=False)
    assert report_exit_code(report) == 2


def test_report_exit_code_rejects_partial_reference_in_complete_report():
    report = _complete_report()
    report["analysis_completeness"]["references"] = [
        {
            "source_path": "SKILL.md",
            "line": 12,
            "target_path": None,
            "status": "missing",
            "disposition": "partial",
        }
    ]
    assert report_exit_code(report) == 2


def test_report_exit_code_accepts_accounted_nonfatal_unresolved_reference():
    report = _complete_report()
    report["analysis_completeness"].update(
        status="partial",
        is_complete=False,
        ledger_exceptions=[
            {
                "outcome": "partial",
                "phase": "reference_resolution",
                "reason_code": "reference_unresolved",
                "path": "SKILL.md",
                "start_line": 12,
                "end_line": 12,
                "fatal": False,
            }
        ],
        references=[
            {
                "source_path": "SKILL.md",
                "line": 12,
                "target_path": None,
                "status": "missing",
                "disposition": "partial",
            },
            {
                "source_path": "SKILL.md",
                "line": 12,
                "target_path": None,
                "status": "missing",
                "disposition": "partial",
            },
        ],
    )
    assert report_exit_code(report) == 0


def test_report_exit_code_rejects_unmatched_unresolved_reference():
    report = _complete_report()
    report["analysis_completeness"].update(
        status="partial",
        is_complete=False,
        ledger_exceptions=[
            {
                "outcome": "partial",
                "phase": "reference_resolution",
                "reason_code": "reference_unresolved",
                "path": "SKILL.md",
                "start_line": 12,
                "end_line": 12,
                "fatal": False,
            }
        ],
    )
    assert report_exit_code(report) == 2


def test_report_exit_code_accepts_explicit_binary_scope_exclusion():
    report = _complete_report()
    report["analysis_completeness"]["scope_exclusions"] = [
        {
            "outcome": "out_of_scope",
            "reason_code": "binary_content",
            "path": "docs/logo.png",
            "analyzers": ["static_patterns_supply_chain"],
        }
    ]
    analyzer = next(
        item
        for item in report["analysis_completeness"]["analyzer_statuses"]
        if item["analyzer_id"] == "static_patterns_supply_chain"
    )
    analyzer.update(planned_work=2, completed=1, failed=1)
    assert report_exit_code(report) == 0


# ── Reviewed static parse limits ──────────────────────────────────────────────
#
# A bounded static parser can stop inside one oversized expression; the scanner then
# marks that analyzer degraded and the file partially inspected. A hand review can
# record a reviewed partial pinned to the file's SHA-256, so any edit reopens it.

PARTIAL_PATH = "README.en.md"
PARTIAL_ANALYZER = "static_patterns_tool_misuse"
REVIEWED = frozenset({(PARTIAL_PATH, PARTIAL_ANALYZER, "static_parse_limit")})


def _report_with_static_partial(*, analyzer=PARTIAL_ANALYZER, path=PARTIAL_PATH):
    report = _complete_report()
    completeness = report["analysis_completeness"]
    completeness.update(
        total_components=2,
        scanned_components=1,
        fully_inspected_files=1,
        partially_inspected_files=1,
        coverage_percent=50.0,
        is_complete=False,
        status="partial",
        limitations=[f"Analyzer {analyzer} status: degraded."],
        ledger_exceptions=[
            {
                "outcome": "partial",
                "phase": "static",
                "reason_code": "static_parse_limit",
                "path": path,
                "start_line": None,
                "end_line": None,
                "fatal": False,
                "analyzers": [analyzer],
            }
        ],
    )
    row = next(item for item in completeness["analyzer_statuses"] if item["analyzer_id"] == analyzer)
    row.update(status="degraded", planned_work=2, completed=1, partial=1)
    return report


def test_unreviewed_static_parse_limit_fails_closed():
    assert report_exit_code(_report_with_static_partial()) == 2


def test_reviewed_static_parse_limit_is_accepted():
    assert report_exit_code(_report_with_static_partial(), REVIEWED) == 0


def test_reviewed_static_parse_limit_does_not_hide_findings():
    report = _report_with_static_partial()
    report["issues"] = [{}]
    assert report_exit_code(report, REVIEWED) == 1


def test_reviewed_partial_for_another_analyzer_does_not_apply():
    report = _report_with_static_partial(analyzer="static_patterns_prompt_injection")
    assert report_exit_code(report, REVIEWED) == 2


def test_reviewed_partial_for_another_file_does_not_apply():
    assert report_exit_code(_report_with_static_partial(path="SKILL.md"), REVIEWED) == 2


def test_reviewed_partial_explains_only_its_own_partial_unit():
    report = _report_with_static_partial()
    row = next(
        item
        for item in report["analysis_completeness"]["analyzer_statuses"]
        if item["analyzer_id"] == PARTIAL_ANALYZER
    )
    row.update(planned_work=3, completed=1, partial=2)
    assert report_exit_code(report, REVIEWED) == 2


def test_reviewed_partial_rejects_unexplained_limitations():
    report = _report_with_static_partial()
    report["analysis_completeness"]["limitations"].append("Something else went wrong.")
    assert report_exit_code(report, REVIEWED) == 2


def test_reviewed_partial_accepts_the_reference_coverage_row_it_causes():
    report = _report_with_static_partial()
    report["analysis_completeness"]["analyzer_statuses"].append(_completed_analyzer("reference_coverage"))
    assert report_exit_code(report, REVIEWED) == 0


def test_reference_coverage_row_without_a_reviewed_partial_fails_closed():
    report = _complete_report()
    report["analysis_completeness"]["analyzer_statuses"].append(_completed_analyzer("reference_coverage"))
    assert report_exit_code(report) == 2


def _baseline(sha256, **extra):
    entry = {
        "path": PARTIAL_PATH,
        "analyzer": PARTIAL_ANALYZER,
        "reason_code": "static_parse_limit",
        "sha256": sha256,
        "reason": "Reviewed by hand.",
    }
    entry.update(extra)
    return {"version": 2, "reviewed_partials": [entry]}


def test_reviewed_partials_bind_to_the_file_content(tmp_path):
    target = tmp_path / PARTIAL_PATH
    target.write_bytes(b"# reviewed")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    assert reviewed_partials(_baseline(digest), tmp_path) == REVIEWED
    target.write_bytes(b"# edited after review")
    assert reviewed_partials(_baseline(digest), tmp_path) == frozenset()


def test_reviewed_partials_require_a_reason(tmp_path):
    with pytest.raises(ValueError):
        reviewed_partials(_baseline("0" * 64, reason="  "), tmp_path)


def test_reviewed_partials_can_list_several_analyzers(tmp_path):
    (tmp_path / PARTIAL_PATH).write_bytes(b"x")
    baseline = _baseline(hashlib.sha256(b"x").hexdigest(), analyzers=[PARTIAL_ANALYZER, "static_patterns_ssrf"])
    del baseline["reviewed_partials"][0]["analyzer"]
    assert reviewed_partials(baseline, tmp_path) == frozenset(
        {(PARTIAL_PATH, PARTIAL_ANALYZER, "static_parse_limit"), (PARTIAL_PATH, "static_patterns_ssrf", "static_parse_limit")}
    )


def test_report_exit_code_accepts_accounted_nonfatal_missing_reference():
    report = _complete_report()
    report["analysis_completeness"].update(
        status="partial",
        is_complete=False,
        ledger_exceptions=[
            {
                "outcome": "partial",
                "phase": "reference_resolution",
                "reason_code": "reference_missing",
                "path": "SKILL.md",
                "start_line": 12,
                "end_line": 12,
                "fatal": False,
            }
        ],
        references=[
            {
                "source_path": "SKILL.md",
                "line": 12,
                "target_path": None,
                "status": "missing",
                "disposition": "partial",
            },
            {
                "source_path": "SKILL.md",
                "line": 12,
                "target_path": None,
                "status": "missing",
                "disposition": "partial",
            },
        ],
    )
    assert report_exit_code(report) == 0


def test_report_exit_code_rejects_unknown_reference_reason():
    report = _complete_report()
    report["analysis_completeness"].update(
        status="partial",
        is_complete=False,
        ledger_exceptions=[
            {
                "outcome": "partial",
                "phase": "reference_resolution",
                "reason_code": "reference_bogus",
                "path": "SKILL.md",
                "start_line": 12,
                "end_line": 12,
                "fatal": False,
            }
        ],
        references=[
            {
                "source_path": "SKILL.md",
                "line": 12,
                "target_path": None,
                "status": "missing",
                "disposition": "partial",
            },
            {
                "source_path": "SKILL.md",
                "line": 12,
                "target_path": None,
                "status": "missing",
                "disposition": "partial",
            },
        ],
    )
    assert report_exit_code(report) == 2


def test_report_exit_code_accepts_explicit_binary_scope_exclusion_counted_as_completed():
    report = _complete_report()
    report["analysis_completeness"]["scope_exclusions"] = [
        {
            "outcome": "out_of_scope",
            "reason_code": "binary_content",
            "path": "docs/logo.png",
            "analyzers": ["static_patterns_supply_chain"],
        }
    ]
    analyzer = next(
        item
        for item in report["analysis_completeness"]["analyzer_statuses"]
        if item["analyzer_id"] == "static_patterns_supply_chain"
    )
    analyzer.update(planned_work=2, completed=2, failed=0)
    assert report_exit_code(report) == 0


# ── Reviewed static parse limits ──────────────────────────────────────────────
#
# A bounded static parser can stop inside one oversized expression; the scanner then
# marks that analyzer degraded and the file partially inspected. A hand review can
# record a reviewed partial pinned to the file's SHA-256, so any edit reopens it.

PARTIAL_PATH = "README.en.md"
PARTIAL_ANALYZER = "static_patterns_tool_misuse"
REVIEWED = frozenset({(PARTIAL_PATH, PARTIAL_ANALYZER, "static_parse_limit")})
