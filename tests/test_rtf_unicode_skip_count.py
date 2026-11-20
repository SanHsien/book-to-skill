"""The RTF fallback parser honours \\ucN when skipping \\uN fallback bytes.

Per the RTF spec, ``\\ucN`` says how many fallback characters follow each
``\\uN`` escape, and a reader that decodes ``\\uN`` must skip that many. Writers
use ``\\uc2`` for double-byte code pages, so a CJK character arrives as
``\\uN`` plus two ``\\'hh`` bytes. Skipping only the first byte leaves the second
behind, and the hex-run decoder then turns it into a stray visible character
(PUA, half-width katakana or U+FFFD) inside the extracted text.
"""

import pytest

from book_to_skill.parsers.rtf import strip_rtf_fallback


def _u(code: int) -> str:
    """The RTF escape for ``code``, built so no tool reads it as a Python escape."""
    return "\\" + "u" + str(code)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Shift-JIS fallbacks for U+3042 (82 a0) and U+3044 (82 a2).
        (
            r"{\rtf1\ansi\ansicpg932\uc2 "
            + _u(12354) + r"\'82\'a0" + _u(12356) + r"\'82\'a2}",
            chr(0x3042) + chr(0x3044),
        ),
        # GBK fallbacks for U+4E2D (d6 d0) and U+6587 (ce c4).
        (
            r"{\rtf1\ansi\ansicpg936\uc2 "
            + _u(20013) + r"\'d6\'d0" + _u(25991) + r"\'ce\'c4}",
            chr(0x4E2D) + chr(0x6587),
        ),
        # A literal two-character fallback.
        (r"{\rtf1\uc2 " + _u(20013) + "??ok}", chr(0x4E2D) + "ok"),
    ],
)
def test_uc2_skips_both_fallback_bytes(raw, expected):
    assert strip_rtf_fallback(raw) == expected


def test_uc0_skips_nothing():
    assert strip_rtf_fallback(r"{\rtf1\uc0 " + _u(945) + " ok}") == chr(945) + "ok"


def test_uc_is_scoped_to_its_group():
    # Inside the group \uc2 applies; after the group closes, \uc1 is back.
    raw = r"{\rtf1 {\uc2 " + _u(20013) + r"\'d6\'d0}" + _u(233) + r"\'e9!}"
    assert strip_rtf_fallback(raw) == chr(0x4E2D) + chr(233) + "!"


def test_fallback_skip_stops_at_group_end():
    # A fallback never extends past the end of the group it is in.
    raw = r"{\rtf1\ansicpg1252 {\uc2 " + _u(233) + r"\'e9}\'e9}"
    assert strip_rtf_fallback(raw) == chr(233) + chr(233)
