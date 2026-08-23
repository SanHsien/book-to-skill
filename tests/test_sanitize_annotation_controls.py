"""Deprecated / interlinear-annotation format controls are stripped too.

These are category Cf, Default_Ignorable code points that render as nothing —
the same invisible format-control shape as the zero-width set — but the original
blocklist missed them, so they passed straight through the extraction scrub (and,
because the scanner shares is_invisible_codepoint, went unflagged there too).
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.sanitize import is_invisible_codepoint, sanitize_extracted_text

# U+206A-206F (deprecated format controls) + U+FFF9-FFFB (interlinear annotation).
ANNOTATION_CONTROLS = "".join(
    chr(cp) for cp in [*range(0x206A, 0x2070), 0xFFF9, 0xFFFA, 0xFFFB]
)


def test_all_annotation_controls_are_invisible():
    assert all(is_invisible_codepoint(ord(c)) for c in ANNOTATION_CONTROLS)


def test_annotation_controls_are_stripped_and_counted():
    text = f"study{ANNOTATION_CONTROLS}advice"
    cleaned, removed = sanitize_extracted_text(text)
    assert cleaned == "studyadvice"
    assert removed == len(ANNOTATION_CONTROLS)


def test_visible_lookalikes_are_kept():
    # A musical symbol is a real So character, not an invisible format control —
    # it must survive.
    #
    # Fork divergence: upstream PR #182 (this file) also asserted that the Braille
    # blank U+2800 survives, while upstream PR #178 strips it as a blank-rendering
    # carrier. Both are open upstream and they contradict each other. This fork
    # adopted both and resolved the overlap towards stripping: the output here is
    # read by an agent, so a character that renders as nothing and survives
    # whitespace normalisation is a smuggling channel, not prose. A book that
    # genuinely discusses Braille loses one blank cell; a skill that silently
    # carries hidden instructions is the worse trade. See docs/UPSTREAM.md.
    text = "ab\U0001D159c"
    cleaned, removed = sanitize_extracted_text(text)
    assert cleaned == text
    assert removed == 0


def test_braille_blank_is_stripped_as_a_blank_carrier():
    cleaned, removed = sanitize_extracted_text("a⠀b")
    assert cleaned == "ab"
    assert removed == 1
