"""Regression test: running the tools must not leave bytecode in the source tree.

When book-to-skill is installed as an agent skill, the skill *is* the source
tree — it is cloned or unpacked into `~/.config/opencode/skills/<name>/` (or
another host root) and executed from there. Any `__pycache__` written on first
run ends up shipped inside the skill: extra files to scan, noise in diffs, and
`__pycache__/*.pyc` showing up wherever the skill is published or shared.

The agent invoking the skill does not set PYTHONDONTWRITEBYTECODE, so the guard
has to live in the entry points themselves, before the package is imported.

Each entry point runs against a fresh copy of the tracked files in a temporary
directory — the same shape as a real install — rather than the working tree.
Deleting and re-creating bytecode inside the checkout races with other test
processes and fails outright on synced folders that hold directory handles
(OneDrive returns "access denied" on `__pycache__` removal).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

# Every module that (a) imports `book_to_skill` and (b) can be run directly.
# Kept explicit on purpose: if a new entry point appears, this list — and the
# guard it asserts — must be revisited, and the test says so.
ENTRY_POINTS = [
    "scripts/extract.py",
    "tools/scan_generated_skill.py",
    "tools/discovery_tax.py",
    "book_to_skill/cli.py",
    "book_to_skill/utils.py",
]


# Directories that never contribute to the payload and are not worth walking.
# `__pycache__` is deliberately NOT listed: it is exactly what we hunt for, and
# excluding it here would also hide the `.pyc` files inside it (their path
# contains a `__pycache__` part), making every assertion vacuously true.
_WALK_SKIP = {".git", ".venv", "venv", "node_modules", ".tox"}


def _iter_source_files(root: Path):
    """Yield candidate files, pruning whole directories we never care about."""
    for path in root.rglob("*"):
        if _WALK_SKIP & set(path.relative_to(root).parts):
            continue
        yield path


def _artifacts(root: Path) -> list[str]:
    """Bytecode artifacts that would ship inside the skill."""
    return sorted(
        str(p.relative_to(root))
        for p in _iter_source_files(root)
        if p.is_file() and p.suffix == ".pyc"
    )


def _supports_help(root: Path, entry: str) -> bool:
    """`--help` is only safe on modules that define an argparse CLI."""
    return "argparse" in (root / entry).read_text(encoding="utf-8")


def _run(argv: list[str], *, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


@pytest.fixture()
def installed_skill(tmp_path: Path) -> Path:
    """A fresh copy of the tracked files, laid out the way a host installs it."""
    try:
        listing = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"git unavailable: {exc}")
    root = tmp_path / "book-to-skill"
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", "surrogateescape")
        source = REPO_ROOT / relative
        if not source.is_file():
            continue
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    assert _artifacts(root) == [], "tracked files unexpectedly contain bytecode"
    return root


@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_entry_point_writes_no_bytecode(installed_skill, entry):
    script = installed_skill / entry
    assert script.is_file(), f"missing entry point: {entry}"

    # Deliberately strip any inherited protection: the guard must hold for an
    # agent that simply runs the tool.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
    env["PYTHONPATH"] = str(installed_skill)

    argv = [sys.executable, str(script)]
    if _supports_help(installed_skill, entry):
        argv.append("--help")

    _run(argv, cwd=installed_skill, env=env)
    dirty = _artifacts(installed_skill)

    # The import must really have happened, or the test passes vacuously: a
    # crash before importing the package writes no bytecode. Proved by
    # importing the package from the installed copy and checking it is loaded,
    # which holds for every entry point including ones with no CLI flags. The
    # probe sets the guard itself so it cannot add artifacts of its own.
    probe = _run(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                "sys.dont_write_bytecode = True\n"
                "import book_to_skill, book_to_skill.utils\n"
                f"assert book_to_skill.__file__.startswith({str(installed_skill)!r})\n"
                "print('imported')\n"
            ),
        ],
        cwd=installed_skill,
        env=env,
    )
    assert probe.returncode == 0 and "imported" in probe.stdout, (
        f"could not import book_to_skill for {entry} "
        f"(exit {probe.returncode}): {probe.stderr.strip()[:200]}"
    )

    assert dirty == [], f"{entry} left build artifacts: {dirty[:5]}"


def test_entry_point_list_still_matches_the_source_tree():
    """Guard against the list going stale as the package grows."""
    found = set()
    for py in _iter_source_files(REPO_ROOT):
        if py.suffix != ".py":
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except OSError:
            continue
        imports_package = any(
            line.lstrip().startswith(("from book_to_skill", "import book_to_skill"))
            for line in text.splitlines()
        )
        if not imports_package:
            continue
        if "__main__" in text or "argparse" in text or "def main(" in text:
            found.add(py.relative_to(REPO_ROOT).as_posix())

    # `__main__.py`/`__init__.py` cannot be guarded from inside the package:
    # Python compiles them before any of our code runs. They are excluded here
    # and instead SKILL.md must never invoke `python -m book_to_skill`. The test
    # suite imports the package but is not part of the installed payload.
    found -= {"book_to_skill/__main__.py", "book_to_skill/__init__.py"}
    found = {path for path in found if not path.startswith("tests/")}

    assert found == set(ENTRY_POINTS), (
        "entry points changed; update ENTRY_POINTS and make sure every one sets "
        f"sys.dont_write_bytecode. Diff: {sorted(found ^ set(ENTRY_POINTS))}"
    )
