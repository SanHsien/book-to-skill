"""tools/validate_skill.py — frontmatter parsing is BOM-tolerant."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "validate_skill", Path(__file__).resolve().parent.parent / "tools" / "validate_skill.py"
)
validate_skill = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(validate_skill)

_SKILL = "---\nname: my-skill\ndescription: A test skill.\n---\n\n# Body\n"


def test_audit_accepts_skill_without_bom(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_bytes(_SKILL.encode("utf-8"))
    errors, _ = validate_skill.audit(str(p))
    assert errors == []


def test_audit_accepts_skill_with_utf8_bom(tmp_path):
    # A SKILL.md saved with a UTF-8 BOM used to fail with "no valid YAML
    # frontmatter" because the BOM broke text.startswith("---").
    p = tmp_path / "SKILL.md"
    p.write_bytes(b"\xef\xbb\xbf" + _SKILL.encode("utf-8"))
    errors, _ = validate_skill.audit(str(p))
    assert errors == []


# --- upstream PR #302: block-scalar `description` ---------------------------------
# `description: |` / `description: >` used to be read as the one-character indicator,
# so the 1024-char cap never fired on a multi-line description.


def _block_skill(indicator, body_lines):
    body = "\n".join("  " + ln for ln in body_lines)
    return f"---\nname: my-skill\ndescription: {indicator}\n{body}\nlicense: MIT\n---\n\n# Body\n"


@pytest.mark.parametrize("indicator", ["|", ">", "|-", ">-", "|+"])
def test_block_scalar_description_over_cap_is_rejected(tmp_path, indicator):
    # A 1,300-char block description must not pass as a 1-char one.
    p = tmp_path / "SKILL.md"
    p.write_text(_block_skill(indicator, ["word " * 20] * 13), encoding="utf-8")
    errors, _ = validate_skill.audit(str(p))
    assert any(e.startswith("description:") and "> 1024" in e for e in errors), errors


@pytest.mark.parametrize("indicator", ["|", ">"])
def test_block_scalar_description_under_cap_is_accepted(tmp_path, indicator):
    p = tmp_path / "SKILL.md"
    p.write_text(_block_skill(indicator, ["A short test skill", "on two lines."]), encoding="utf-8")
    errors, _ = validate_skill.audit(str(p))
    assert errors == []


def test_block_scalar_value_is_read_from_the_indented_lines():
    fm = "name: my-skill\ndescription: >\n  first line\n  second line\n\n  new paragraph\nlicense: MIT\n"
    assert validate_skill.get_scalar(fm, "description") == "first line second line\nnew paragraph"
    fm = "name: my-skill\ndescription: |\n  first line\n  second line\nlicense: MIT\n"
    assert validate_skill.get_scalar(fm, "description") == "first line\nsecond line"


def test_empty_block_scalar_description_is_missing(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: my-skill\ndescription: |\nlicense: MIT\n---\n\n# Body\n", encoding="utf-8")
    errors, _ = validate_skill.audit(str(p))
    assert "description: missing (required)" in errors
