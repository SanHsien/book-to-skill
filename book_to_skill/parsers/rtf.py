import codecs
import html
import re
import sys
from book_to_skill.parsers.text import read_text_file
from book_to_skill.exceptions import ExtractionError


# RTF unicode escape: \uN (signed decimal), and \ucN, which says how many
# fallback characters follow each \uN for readers that cannot decode it. A
# reader that decodes \uN must skip that many (RTF spec; the default is \uc1).
# \ucN is scoped to its group, so braces are tracked too.
_RTF_UNICODE_TOKEN = re.compile(r"\\uc(\d+) ?|\\u(-?\d+) ?|[{}]")
_RTF_HEX_BYTE = re.compile(r"\\'[0-9a-fA-F]{2}")
_RTF_HEX_RUN = re.compile(r"(?:\\'[0-9a-fA-F]{2})+")
_RTF_ANSI_CODEPAGE = re.compile(r"\\ansicpg(\d+)")


def _rtf_unicode_repl(code: int) -> str:
    if code == 0 or 0xD800 <= code <= 0xDFFF:   # NUL and lone surrogates: unwanted in text
        return ""
    return chr(code)


def _skip_unicode_fallback(raw: str, index: int, count: int) -> tuple[int, int]:
    r"""Skip the ``count`` fallback characters at ``index``.

    Returns the index after them and the number of groups opened on the way.

    A fallback character is one ``\'hh`` byte or one literal character. CR and
    LF are ignored, as everywhere in an RTF body: writers wrap long lines at any
    point, so they neither count nor end the skip. Opening a group copies the
    reader state, pending skip included, so the skip continues into it; the
    caller must enter those groups in its own scope tracking. The end of a
    group ends the skip. The skip also stops at other whitespace and at any
    other control word: the spec would count those too, but in practice they
    mean the writer left the fallback out, and swallowing them would lose real
    text (for example the next ``\uN`` of a surrogate pair).
    """
    length = len(raw)
    opened = 0
    while count > 0 and index < length:
        char = raw[index]
        if char in "\r\n":
            index += 1
            continue
        if char == "{":
            index += 1
            opened += 1
            continue
        hex_byte = _RTF_HEX_BYTE.match(raw, index)
        if hex_byte:
            index = hex_byte.end()
        elif char in "\\}" or char.isspace():
            break
        else:
            index += 1
        count -= 1
    return index, opened


def _decode_rtf_unicode(raw: str) -> str:
    r"""Decode \uN escapes, skip their fallbacks and pair UTF-16 surrogates."""
    out: list[str] = []
    cursor = 0
    skip = 1                 # current \ucN value
    saved: list[int] = []    # \ucN of the enclosing groups
    pending_high = None      # (code, end of its fallback, index in out)
    position = 0
    while True:
        match = _RTF_UNICODE_TOKEN.search(raw, position)
        if match is None:
            break
        token = match.group(0)
        if token == "{":
            saved.append(skip)
            position = match.end()
            continue
        if token == "}":
            if saved:
                skip = saved.pop()
            position = match.end()
            continue
        out.append(raw[cursor:match.start()])
        if match.group(1) is not None:
            skip = int(match.group(1))
            cursor = position = match.end()
            continue
        code = int(match.group(2)) % 0x10000   # RTF uses signed 16-bit; wrap negatives
        end, opened = _skip_unicode_fallback(raw, match.end(), skip)
        saved.extend([skip] * opened)   # groups entered inside the fallback
        if (
            pending_high is not None
            and pending_high[1] == match.start()
            and 0xDC00 <= code <= 0xDFFF
        ):
            high = pending_high[0]
            out[pending_high[2]] = chr(0x10000 + (high - 0xD800) * 0x400 + code - 0xDC00)
            pending_high = None
        elif 0xD800 <= code <= 0xDBFF:
            out.append("")     # dropped unless a low surrogate follows directly
            pending_high = (code, end, len(out) - 1)
        else:
            out.append(_rtf_unicode_repl(code))
            pending_high = None
        cursor = position = end
    out.append(raw[cursor:])
    return "".join(out)


def _rtf_ansi_encoding(raw: str) -> str:
    """Return the declared ANSI code page, defaulting to Windows-1252."""
    match = _RTF_ANSI_CODEPAGE.search(raw)
    encoding = f"cp{match.group(1)}" if match else "cp1252"
    try:
        codecs.lookup(encoding)
    except LookupError:
        return "cp1252"
    return encoding


def _decode_hex_run(match: re.Match, encoding: str) -> str:
    payload = bytes(
        int(value, 16)
        for value in re.findall(r"[0-9a-fA-F]{2}", match.group(0))
    )
    return payload.decode(encoding, errors="replace")


# RTF groups whose contents are metadata or formatting tables rather than
# document text. Stripping only the control words inside them (what the cleanup
# below does) leaves the residue behind: font and style *names*, the generator
# string, and the \info title/author all end up in the extracted book text.
_SKIP_DESTINATIONS = frozenset({
    "fonttbl",            # {\fonttbl{\f0\fnil Calibri;}}   -> "Calibri;"
    "colortbl",           # {\colortbl;\red255...;}          -> ";;;"
    "stylesheet",         # {\stylesheet{\s0 Normal;}}       -> "Normal;"
    "info",               # {\info{\title X}{\author Y}}     -> "XY"
    "listtable", "listoverridetable", "revtbl", "rsidtbl",
    "latentstyles", "datastore", "themedata", "colorschememapping",
    "filetbl", "xmlnstbl", "pgptbl", "protusertbl", "userprops",
    "docvar",
    "pict", "objdata",    # binary image / OLE payloads as hex text
    "bkmkstart", "bkmkend",
})

# The first control word of a group, allowing the "\*" ignorable-destination
# prefix: "{\fonttbl", "{\*\generator", "{\*\bkmkstart".
_GROUP_DESTINATION = re.compile(r"\\\*?\\?([a-zA-Z]+)")


def _strip_destination_groups(raw: str) -> str:
    """Remove RTF groups that hold no document text.

    Tracks brace depth so a whole group is dropped, not just its control words.
    Per the RTF spec a reader that does not understand a ``\\*`` destination must
    skip the entire group, which also handles ``\\*\\generator`` and any vendor
    extension without naming it. Escaped ``\\{`` / ``\\}`` / ``\\\\`` are not
    treated as delimiters.

    A useful side effect: for a field, ``{\\field{\\*\\fldinst HYPERLINK ...}
    {\\fldrslt visible text}}`` keeps the result and drops the instruction.
    """
    out: list[str] = []
    index = 0
    depth = 0
    skip_at_depth = 0  # non-zero while inside a skipped group
    length = len(raw)

    while index < length:
        char = raw[index]

        # Escaped literal: "\{", "\}", "\\" are text, never group delimiters.
        if char == "\\" and index + 1 < length and raw[index + 1] in "{}\\":
            if not skip_at_depth:
                out.append(raw[index:index + 2])
            index += 2
            continue

        if char == "{":
            depth += 1
            if not skip_at_depth:
                match = _GROUP_DESTINATION.match(raw, index + 1)
                ignorable = raw.startswith("{\\*", index)
                if ignorable or (match and match.group(1) in _SKIP_DESTINATIONS):
                    skip_at_depth = depth
                else:
                    out.append(char)
            index += 1
            continue

        if char == "}":
            if skip_at_depth and depth == skip_at_depth:
                skip_at_depth = 0
            elif not skip_at_depth:
                out.append(char)
            depth -= 1
            index += 1
            continue

        if not skip_at_depth:
            out.append(char)
        index += 1

    if skip_at_depth:
        # Unterminated destination group: the file is malformed and everything
        # after the unclosed brace was just dropped, which could be the whole
        # book. Leaking some metadata residue is the lesser evil, so fall back
        # to the unscanned text rather than returning a truncated document.
        return raw

    return "".join(out)


def strip_rtf_fallback(raw: str) -> str:
    # Drop metadata/table groups wholesale first, so their contents never reach
    # the control-word cleanup that would otherwise strip the markup and leave
    # the names behind as if they were prose.
    raw = _strip_destination_groups(raw)
    # Park escaped literals before ANY control processing: the second slash in
    # "\\\\u945?" or "\\\\tab" belongs to displayed text, not an active control.
    # Do this after destination scanning, which needs the original braces and
    # escapes to identify whole non-content groups. Longest escape first.
    raw = (
        raw.replace("\\\\", "\x01")
        .replace("\\{", "\x02")
        .replace("\\}", "\x03")
    )
    ansi_encoding = _rtf_ansi_encoding(raw)
    raw = _decode_rtf_unicode(raw)   # decode \uN escapes first
    # Hex bytes immediately following \uN are its compatibility fallback and
    # were skipped above, as many as \ucN says. Any remaining \'hh escapes are actual
    # document text. Decode adjacent bytes as a run so multibyte code pages work.
    raw = _RTF_HEX_RUN.sub(
        lambda match: _decode_hex_run(match, ansi_encoding), raw
    )
    # \line is a required line break; do not match longer control words such
    # as \linebetcol. A single following space is an RTF delimiter, not text.
    raw = re.sub(r"\\line(?![a-zA-Z])(?:-?\d+)? ?", "\n", raw)
    raw = re.sub(r"\\par[d]?", "\n", raw)
    raw = re.sub(r"\\tab", "\t", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)
    raw = raw.replace("{", "").replace("}", "")
    raw = raw.replace("\x01", "\\").replace("\x02", "{").replace("\x03", "}")
    return html.unescape(raw)


def extract_rtf(rtf_path: str) -> tuple[str, str]:
    raw = read_text_file(rtf_path)
    if raw is None:
        raise ExtractionError(f"Could not read RTF file: {rtf_path}")

    try:
        from striprtf.striprtf import rtf_to_text
        text = rtf_to_text(raw)
        if text.strip():
            return text, "striprtf"
    except ImportError:
        pass
    except Exception as e:
        print(f"  [warn] extract_rtf/striprtf failed: {type(e).__name__}: {e}", file=sys.stderr)

    return strip_rtf_fallback(raw), "rtf-regex"
