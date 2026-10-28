"""Synthetic EPUBs exercise UTF-16 XML in the stdlib fallback."""

import codecs
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from book_to_skill import utils
from book_to_skill.parsers import epub


ROOT = Path(__file__).resolve().parent.parent


def _encode_xml(text: str, encoding: str) -> bytes:
    declaration = '<?xml version="1.0" encoding="{}"?>'.format(
        "UTF-8" if encoding == "utf-8" else "UTF-16"
    )
    data = (declaration + text).encode(encoding)
    if encoding == "utf-16-le":
        return codecs.BOM_UTF16_LE + data
    if encoding == "utf-16-be":
        return codecs.BOM_UTF16_BE + data
    return data


def _make_epub(path: Path, *, opf_encoding: str, chapter_encoding: str,
               container_encoding: str = "utf-8") -> None:
    container = (
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        '<rootfiles><rootfile full-path="OEBPS/book.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    opf = (
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<manifest><item id="first" href="z.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="second" href="a.xhtml" media-type="application/xhtml+xml"/>'
        '</manifest><spine><itemref idref="first"/><itemref idref="second"/>'
        '</spine></package>'
    )
    first = '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>FIRST 中文</p></body></html>'
    second = '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>SECOND café</p></body></html>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", _encode_xml(container, container_encoding))
        # A decoy comes first so a failed container lookup cannot accidentally
        # pick the intended OPF via the fallback archive scan.
        archive.writestr("decoy.opf", '<package><manifest/></package>')
        archive.writestr("OEBPS/book.opf", _encode_xml(opf, opf_encoding))
        archive.writestr("OEBPS/z.xhtml", _encode_xml(first, chapter_encoding))
        archive.writestr("OEBPS/a.xhtml", _encode_xml(second, chapter_encoding))


class TestEpubUtf16Fallback(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "synthetic.epub"

    def assert_complete(self):
        text = epub.extract_with_zipfile(str(self.path))
        self.assertIsNotNone(text)
        self.assertEqual(text, "FIRST 中文\n\nSECOND café")
        self.assertEqual(epub.count_epub_chapters(str(self.path)), 2)

    def test_utf16_content_documents_preserve_text_and_spine_order(self):
        for encoding in ("utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding):
                _make_epub(self.path, opf_encoding="utf-8", chapter_encoding=encoding)
                self.assert_complete()

    def test_utf16_package_document_preserves_spine_order_and_count(self):
        for encoding in ("utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding):
                _make_epub(self.path, opf_encoding=encoding, chapter_encoding="utf-8")
                self.assert_complete()

    def test_utf16_container_uses_declared_package_instead_of_decoy(self):
        for encoding in ("utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding):
                _make_epub(self.path, opf_encoding="utf-8", chapter_encoding="utf-8",
                           container_encoding=encoding)
                self.assert_complete()

    def test_existing_utf8_archive_is_unchanged(self):
        _make_epub(self.path, opf_encoding="utf-8", chapter_encoding="utf-8")
        self.assert_complete()

    def test_utf32_le_bom_does_not_trigger_utf16_detection(self):
        # UTF-32 is not an EPUB XML encoding, but its LE BOM begins with the
        # UTF-16 LE BOM. Preserve the old UTF-8 replacement behavior.
        raw = codecs.BOM_UTF32_LE + "<p>Example</p>".encode("utf-32-le")
        self.assertEqual(epub._decode_epub_xml(raw), raw.decode("utf-8", errors="replace"))

    def test_dispatcher_reports_zipfile_and_utf16_spine_count(self):
        _make_epub(self.path, opf_encoding="utf-16-le", chapter_encoding="utf-16-be")
        with patch.object(utils, "prepare_dependencies"), patch.object(
            utils, "extract_with_ebooklib", return_value=None
        ):
            result = utils.extract_single_file(self.path, "text", "no")
        self.assertEqual(result["extraction_method"], "zipfile")
        self.assertEqual(result["spine_items"], 2)
        self.assertEqual(result["text"], "FIRST 中文\n\nSECOND café")

    def test_real_cli_without_optional_dependencies(self):
        _make_epub(self.path, opf_encoding="utf-16-be", chapter_encoding="utf-16-le")
        output = Path(self.temporary.name) / "work"
        env = os.environ.copy()
        env["BOOK_SKILL_WORKDIR"] = str(output)
        result = subprocess.run(
            [sys.executable, "-B", "-S", str(ROOT / "scripts" / "extract.py"),
             str(self.path), "--mode", "text", "--install-missing", "no"],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        corpus = (output / "full_text.txt").read_text(encoding="utf-8")
        metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
        self.assertIn("FIRST 中文\n\nSECOND café", corpus)
        self.assertEqual(metadata["sources"][0]["extraction_method"], "zipfile")
        self.assertEqual(metadata["sources"][0]["pages_label"], "spine_items")
        self.assertEqual(metadata["sources"][0]["pages"], 2)
