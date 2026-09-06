"""Run the pinned SkillSpector graph deterministically for the repo gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _invoke_graph(graph, state):
    """Serialize analyzer branches to prevent nondeterministic finding loss/gain."""
    return graph.invoke(state, config={"max_concurrency": 1})


def _build_state(scan_state, *, input_path, output_format, baseline):
    return scan_state(
        input_path,
        output_format,
        True,
        baseline=baseline,
        show_suppressed=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()

    result = None
    try:
        from skillspector.cleanup import cleanup_result
        from skillspector.cli import FormatChoice, _result_body, _scan_state, graph

        state = _build_state(
            _scan_state,
            input_path=args.input_path,
            output_format=FormatChoice.json,
            baseline=args.baseline,
        )
        result = _invoke_graph(graph, state)
        report_body = _result_body(result)
        if not report_body:
            raise RuntimeError("SkillSpector returned an empty report")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report_body, encoding="utf-8", newline="\n")
        report = json.loads(report_body)
        if result.get("execution_successful") is not True:
            return 2
        issues = report.get("issues")
        if not isinstance(issues, list):
            return 2
        return 1 if issues else 0
    except Exception as exc:
        print(f"SkillSpector scan failed: {exc}", file=sys.stderr)
        return 2
    finally:
        if result is not None:
            cleanup_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
