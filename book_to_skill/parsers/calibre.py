from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import sys
from book_to_skill.config import OUTPUT_DIR

_OUTPUT_SEQ = itertools.count()


def extract_with_ebook_convert(input_path: str) -> str | None:
    if not shutil.which("ebook-convert"):
        return None
    # A name unique to this call: the work directory is shared by every source in
    # a batch, so a fixed name let a conversion that reports success without
    # writing anything be satisfied by an earlier source's file — one book's text
    # recorded under another source's name. The pid keeps it unique across runs
    # that share a BOOK_SKILL_WORKDIR.
    output_path = OUTPUT_DIR / f"ebook-convert-output-{os.getpid()}-{next(_OUTPUT_SEQ)}.txt"
    try:
        input_path = os.path.abspath(input_path)
        result = subprocess.run(
            ["ebook-convert", input_path, str(output_path)],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0 and output_path.exists():
            text = output_path.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                return text
    except Exception as e:
        print(f"  [warn] extract_with_ebook_convert failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None
