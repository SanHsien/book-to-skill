from tools.check_skillspector_report import report_exit_code


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
    next(item for item in statuses if item["analyzer_id"] == "meta_analyzer").update(
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
