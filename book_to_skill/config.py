import os
import tempfile
from pathlib import Path


def default_output_dir() -> Path:
    """Work directory for extracted text and metadata.

    ``BOOK_SKILL_WORKDIR`` always wins. Otherwise Windows uses a per-user
    ``%LOCALAPPDATA%\\book-to-skill\\work`` path instead of the shared
    ``%TEMP%\\book_skill_work`` default, which is predictable on multi-user
    machines. POSIX keeps ``<tempdir>/book_skill_work``.
    """
    override = os.environ.get("BOOK_SKILL_WORKDIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "book-to-skill" / "work"
        return Path.home() / "AppData" / "Local" / "book-to-skill" / "work"
    return Path(tempfile.gettempdir()) / "book_skill_work"


OUTPUT_DIR = default_output_dir()
OUTPUT_TEXT = OUTPUT_DIR / "full_text.txt"
OUTPUT_META = OUTPUT_DIR / "metadata.json"

WORDS_PER_TOKEN = 0.75  # approximate (Latin / whitespace-delimited text)
# CJK scripts carry little or no whitespace, so word-splitting under-counts them
# by orders of magnitude. Count CJK codepoints directly against this
# chars-per-token ratio instead (see estimate_tokens in utils.py).
CJK_CHARS_PER_TOKEN = 1.5  # approximate for cl100k-style tokenizers

TEXT_EXTENSIONS = {".txt", ".text", ".md", ".markdown", ".rst", ".adoc", ".asciidoc"}
HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
CALIBRE_EBOOK_EXTENSIONS = {".mobi", ".azw", ".azw3"}
SUPPORTED_EXTENSIONS = {
    ".pdf", ".epub", ".docx", ".rtf",
    *TEXT_EXTENSIONS,
    *HTML_EXTENSIONS,
    *CALIBRE_EBOOK_EXTENSIONS,
}

PYTHON_DEPENDENCIES = {
    "docling": "docling",
    "pypdf": "pypdf",
    "pdfminer": "pdfminer.six",
    "ebooklib": "ebooklib",
    "bs4": "beautifulsoup4",
    "docx": "python-docx",
    "striprtf": "striprtf",
    "trafilatura": "trafilatura",
}


def supported_formats_message() -> str:
    return ", ".join(sorted(SUPPORTED_EXTENSIONS))
