"""sanitize_extracted_text classifies distinct characters, not every character.

The per-distinct-character rewrite (with an ASCII early return) is a speed-up
only. It must keep the exact policy of the original per-character loop: same
output, same removal count, folds not counted. The reference below is that
original loop, kept here so any drift in either direction fails a test.
"""

import random
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.sanitize import (
    fold_cjk_radicals,
    is_invisible_codepoint,
    sanitize_extracted_text,
)


def _reference(text: str) -> tuple[str, int]:
    kept = []
    removed = 0
    for character in fold_cjk_radicals(text):
        if is_invisible_codepoint(ord(character)):
            removed += 1
            continue
        kept.append(character)
    return "".join(kept), removed


def test_every_code_point_matches_the_per_character_reference():
    # One string with every code point once (including lone surrogates).
    everything = "".join(chr(cp) for cp in range(0x110000))
    assert sanitize_extracted_text(everything) == _reference(everything)


def test_each_code_point_alone_matches_the_reference_for_the_policy_sets():
    interesting = [
        *range(0x00, 0x80),
        *range(0x200B, 0x2070),
        *range(0x2F00, 0x2FE0),
        *range(0xFE00, 0xFE10),
        0xFEFF, 0xFFF9, 0xFFFA, 0xFFFB,
        *range(0x1D173, 0x1D17B),
        *range(0xE0000, 0xE0080),
        *range(0xE0100, 0xE01F0),
    ]
    for cp in interesting:
        text = f"a{chr(cp)}b{chr(cp)}"
        assert sanitize_extracted_text(text) == _reference(text), hex(cp)


def test_repeated_and_mixed_characters_match_the_reference():
    rng = random.Random(20261028)
    pool = [
        "a", " ", "\n", "中", "⼀", "⽊", "פ", "\U0001f642",
        *(chr(cp) for cp in (0x200B, 0x202B, 0xFE0F, 0xE0041, 0xFFF9)),
    ]
    for _ in range(200):
        text = "".join(rng.choice(pool) for _ in range(rng.randint(0, 60)))
        assert sanitize_extracted_text(text) == _reference(text), repr(text)


def test_ascii_input_is_returned_unchanged_with_zero_removed():
    text = "plain ASCII\twith\r\nnewlines and control \x00\x1f chars"
    out, removed = sanitize_extracted_text(text)
    assert out == text
    assert removed == 0


def test_kangxi_fold_is_applied_but_not_counted_as_removal():
    out, removed = sanitize_extracted_text("⼀" + chr(0x200B) + "⼀")
    assert out == "一一"
    assert removed == 1
