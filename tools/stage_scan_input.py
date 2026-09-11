"""Stage the files a SkillSpector gate scans, with the line endings CI sees.

Exact baseline fingerprints hash file content. A checkout made before
``.gitattributes`` existed can keep CRLF text files in its working tree while
the index -- and therefore every CI checkout -- holds LF. Scanning that working
tree directly makes every baselined finding in those files look new, so the
local gate stays red whatever changes. This copies each file the gate should
scan into a staging directory and rewrites CRLF to LF for text files whose
index copy is LF and whose attributes do not ask for CRLF. Binary files, files
git does not track yet, and ``eol=crlf`` files are copied byte for byte.

The file set is ``git ls-files --cached --others --exclude-standard`` for the
given pathspecs: what a clone ships plus files not yet committed, without
gitignored local artifacts.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence


def _git(repo: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
    )
    return completed.stdout


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", "surrogateescape")


def index_line_endings(repo: Path) -> dict[str, str]:
    """Map each tracked path to its ``git ls-files --eol`` metadata."""
    result: dict[str, str] = {}
    for entry in _git(repo, "ls-files", "--eol", "-z").split(b"\0"):
        meta, separator, path = entry.partition(b"\t")
        if separator:
            result[_decode(path)] = _decode(meta)
    return result


def wants_lf(meta: str) -> bool:
    """True when git stores the file as LF text and checks it out as LF."""
    fields = meta.split()
    return bool(fields) and fields[0] == "i/lf" and "eol=crlf" not in meta


def files_to_stage(repo: Path, pathspecs: Sequence[str]) -> list[str]:
    raw = _git(
        repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *pathspecs
    )
    return sorted({_decode(path) for path in raw.split(b"\0") if path})


def stage(
    repo: Path,
    destination: Path,
    pathspecs: Sequence[str] = (),
    exclude: Iterable[str] = (),
) -> tuple[int, int]:
    """Copy the scan input into *destination*; return (staged, normalized) counts."""
    repo = Path(repo)
    destination = Path(destination)
    line_endings = index_line_endings(repo)
    excluded = set(exclude)
    staged = normalized = 0
    for relative in files_to_stage(repo, list(pathspecs)):
        if relative in excluded:
            continue
        source = repo / relative
        if not source.is_file():
            continue
        data = source.read_bytes()
        if wants_lf(line_endings.get(relative, "")) and b"\r\n" in data:
            data = data.replace(b"\r\n", b"\n")
            normalized += 1
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        staged += 1
    return staged, normalized


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage SkillSpector scan input with the line endings CI checks out."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Repository-relative path to leave out; repeatable.",
    )
    parser.add_argument("pathspec", nargs="*", help="Limit staging to these git pathspecs.")
    args = parser.parse_args(argv)
    try:
        staged, normalized = stage(args.repo, args.dest, args.pathspec, args.exclude)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"staging failed: {exc}", file=sys.stderr)
        return 2
    print(f"staged {staged} file(s); {normalized} CRLF text file(s) normalized to LF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
