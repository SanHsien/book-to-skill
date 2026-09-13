"""ToC detection must survive Markdown/AsciiDoc heading markup.

Kept in its own file so it does not collide with upstream edits to
test_book_to_skill.py on a future pull.

Before this fix, _TOC_PATTERN was ^\\s*(table of contents|contents|...)\\s*$,
which requires the header alone on its line. Every Markdown document writes it
as "## Table of Contents", so has_toc was False for the entire Markdown corpus
and detect_structure emitted a spurious "chapter mapping may miss or duplicate
sections" warning. This is the same blind spot #91/#92 fixed for chapter
headings; the sibling ToC pattern was left behind.
"""
import pytest

from book_to_skill.utils import _TOC_PATTERN, detect_structure


@pytest.mark.parametrize("line", [
    "Table of Contents",            # bare (the only form that worked before)
    "  Contents",                   # indented
    "# Contents",                   # ATX level 1
    "## Table of Contents",         # ATX level 2 — the common Markdown form
    "###### Contents",              # ATX level 6
    "== Table of Contents",         # AsciiDoc
    "**Contents**",                 # bold
    "__Table of Contents__",        # bold, underscore form
    "*Contents*",                   # italic
    "## **Table of Contents**",     # heading + bold
    "Contents:",                    # trailing colon
    "## Table of Contents  ",       # trailing whitespace
    "## SUMÁRIO",                   # non-English, uppercase
    "## 目录",                       # CJK
    "目次：",                        # CJK with fullwidth colon
    "## Inhaltsverzeichnis",
    "## Table des matières",
])
def test_toc_header_forms_are_detected(line):
    assert _TOC_PATTERN.search(line), f"should match: {line!r}"


@pytest.mark.parametrize("line", [
    "the contents of this chapter are",   # inline prose
    "Contents of the box",                # line does not end at the header
    "Table of Contents for Part II",      # qualified, not a bare header
    "No table of contents was provided",
    "discontents",                        # substring, not a header
])
def test_prose_mentions_are_not_detected(line):
    assert not _TOC_PATTERN.search(line), f"should NOT match: {line!r}"


def test_markdown_document_reports_has_toc():
    """End-to-end: the regression this fix targets."""
    doc = (
        "# The Decision Ledger\n\n"
        "## Table of Contents\n\n"
        "- Chapter 1 - The Reversibility Gate\n"
        "- Chapter 2 - The Cost-of-Delay Triangle\n\n"
        "## Chapter 1 - The Reversibility Gate\n\nBody text.\n\n"
        "## Chapter 2 - The Cost-of-Delay Triangle\n\nMore body text.\n"
    )
    result = detect_structure(doc)
    assert result["has_toc"] is True
    assert result["chapters_detected"] == 2


def test_document_without_toc_still_reports_false():
    doc = (
        "# Some Book\n\n"
        "## Chapter 1 - Opening\n\nBody text mentioning the contents of the room.\n"
    )
    assert detect_structure(doc)["has_toc"] is False


def test_a_crlf_document_still_detects_its_toc():
    """Windows text keeps CRLF, and `$` in MULTILINE matches before the \\n only.

    The heading-markup pattern this file covers was ported from upstream
    PR #126, whose trailing class is `[ \\t]*$`. On CRLF input the `\\r` sits
    between the header and the line end, so that pattern matches nothing --
    every ToC on this fork's primary platform would have gone undetected, and
    the only visible symptom is a "No table of contents detected" warning that
    looks like a property of the document.
    """
    doc = "## Table of Contents\r\n\r\n1. Chapter 1\r\n2. Chapter 2\r\n\r\n# Chapter 1\r\n\r\nBody.\r\n"

    assert detect_structure(doc)["has_toc"] is True


def test_crlf_applies_to_the_cjk_and_emphasis_forms_too():
    for header in ("目錄\r\n", "**Contents**\r\n", "== Contents\r\n", "Contents:\r\n"):
        assert detect_structure(f"{header}\r\n1. First\r\n")["has_toc"] is True, header


def test_a_punctuation_only_setext_title_is_not_a_chapter():
    """The same string must not be rejected as ATX and accepted as setext.

    `_structural_chapter_count` has two heading branches. The ATX branch rejects
    a title with no word character, which is what keeps a `=====` table border or
    a `***` thematic break out of the count. The setext branch had no equivalent,
    so two thematic breaks in a row minted a phantom chapter -- and a phantom
    chapter is invisible in the output, it just shifts the number the user is
    asked to trust. Adopted from upstream PR #180.
    """
    assert detect_structure("Intro line\n!!!\n---\n\nBody.\n")["chapters_detected"] == 0
    assert detect_structure("Body\n***\n---\n\nMore.\n")["chapters_detected"] == 0
    assert detect_structure("Row\n...\n---\n\nMore.\n")["chapters_detected"] == 0


def test_a_real_setext_title_is_still_counted():
    """The guard must not cost the case it exists to protect."""
    doc = "First Title\n===========\n\nBody.\n\nSecond Title\n============\n\nMore.\n"

    assert detect_structure(doc)["chapters_detected"] == 2
