from tools import run_skillspector


class _FakeGraph:
    def __init__(self) -> None:
        self.calls = []

    def invoke(self, state, config=None):
        self.calls.append((state, config))
        return {"ok": True}


def test_graph_is_invoked_sequentially():
    graph = _FakeGraph()
    result = run_skillspector._invoke_graph(graph, {"input_path": "skill"})
    assert result == {"ok": True}
    assert graph.calls == [
        ({"input_path": "skill"}, {"max_concurrency": 1})
    ]


def test_scan_state_keeps_suppressed_findings_for_stable_partitioning():
    calls = []

    def scan_state(input_path, output_format, no_llm, **kwargs):
        calls.append((input_path, output_format, no_llm, kwargs))
        return {"input_path": input_path}

    state = run_skillspector._build_state(
        scan_state,
        input_path="skill",
        output_format="json",
        baseline="baseline.yaml",
    )
    assert state == {"input_path": "skill"}
    assert calls == [
        (
            "skill",
            "json",
            True,
            {"baseline": "baseline.yaml", "show_suppressed": True},
        )
    ]
