"""依賴新鮮度檢查器：hold 與 deferral 兩條出口。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_dependency_freshness", ROOT / "tools" / "check_dependency_freshness.py"
)
assert _spec is not None and _spec.loader is not None
freshness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(freshness)



# 紅燈的兩條正當出口：長期政策用 hold，這次不升用 deferral。

def test_hold_marker_binds_to_the_package_on_that_line() -> None:
    holds = freshness.parse_holds(
        'dependencies = ["pytest>=8.3"]  # freshness-hold: 矩陣還有 py3.9\n'
        'other = ["ruff>=0.16"]\n'
    )

    assert holds == {"pytest": "矩陣還有 py3.9"}


def test_a_comment_without_the_marker_is_not_a_hold() -> None:
    assert freshness.parse_holds('x = ["ruff>=0.16"]  # 一般註解\n') == {}


def test_deferral_without_a_reviewed_release_is_ignored(tmp_path) -> None:
    # 沒有 deferredLatest 就等於永久靜音，直接忽略。
    path = tmp_path / "deferrals.json"
    path.write_text('{"deferrals": {"ruff": {"reason": "later"}}}', encoding="utf-8")

    assert freshness.load_deferrals(path) == {}


def test_deferral_with_a_reviewed_release_is_read(tmp_path) -> None:
    path = tmp_path / "deferrals.json"
    path.write_text(
        '{"deferrals": {"ruff": {"deferredLatest": "0.16.4", "reason": "要先跑 Windows"}}}',
        encoding="utf-8",
    )

    assert freshness.load_deferrals(path) == {"ruff": ("0.16.4", "要先跑 Windows")}


def test_missing_deferrals_file_defers_nothing(tmp_path) -> None:
    assert freshness.load_deferrals(tmp_path / "absent.json") == {}


def test_aged_floor_needs_review_unless_held_or_deferred() -> None:
    assert freshness.needs_review({"outdated": True, "hold": "", "deferred_reason": ""})
    assert not freshness.needs_review({"outdated": True, "hold": "政策", "deferred_reason": ""})
    assert not freshness.needs_review(
        {"outdated": True, "hold": "", "deferred_reason": "已評估，等 Windows 驗證"}
    )
