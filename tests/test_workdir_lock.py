"""Concurrent extractions must not silently share one workdir.

Kept in its own file so it does not collide with upstream edits to
test_book_to_skill.py on a future pull.

BOOK_SKILL_WORKDIR defaults to a single <tempdir>/book_skill_work for every
run, so two extractions running at once overwrite each other's full_text.txt.
The damage is silent: the losing run still writes its own metadata.json, which
then describes text it did not produce. claim_workdir() makes the second run
refuse to start instead.
"""
import os
import subprocess
import sys

import pytest

import book_to_skill.utils as utils
from book_to_skill.exceptions import ExtractionError
from book_to_skill.utils import claim_workdir, release_workdir, _WORKDIR_LOCK_NAME


def test_claim_creates_workdir_and_lock(tmp_path):
    wd = tmp_path / "work"
    claim_workdir(wd)
    assert wd.is_dir()
    assert (wd / _WORKDIR_LOCK_NAME).read_text().strip() == str(os.getpid())


def test_same_process_can_reclaim(tmp_path):
    """Re-entry within one run is not a collision."""
    wd = tmp_path / "work"
    claim_workdir(wd)
    claim_workdir(wd)  # must not raise


def test_live_holder_blocks_second_run(tmp_path):
    """A different, living PID means a concurrent run: refuse.

    Upstream's version wrote PID 1 as "always exists and is never this process".
    That is a POSIX assumption: on Windows there is no PID 1, and `os.kill(1, 0)`
    raises `OSError [WinError 87]`, which the liveness probe correctly reads as a
    stale lock -- so the test failed on the platform this fork exists for.
    Spawning a real child proves the same thing on every platform.
    """
    wd = tmp_path / "work"
    wd.mkdir()
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (wd / _WORKDIR_LOCK_NAME).write_text(str(holder.pid))

        with pytest.raises(ExtractionError) as exc:
            claim_workdir(wd)
        assert holder.poll() is None, "a liveness check must not terminate the holder"
    finally:
        holder.terminate()
        holder.wait(timeout=10)
    msg = str(exc.value)
    assert "already in use" in msg
    assert "BOOK_SKILL_WORKDIR" in msg, "the error must name the way out"


def test_stale_lock_is_reclaimed(tmp_path):
    """A crashed run must not wedge the next one."""
    wd = tmp_path / "work"
    wd.mkdir()
    dead = _find_unused_pid()
    (wd / _WORKDIR_LOCK_NAME).write_text(str(dead))

    claim_workdir(wd)  # must not raise
    assert (wd / _WORKDIR_LOCK_NAME).read_text().strip() == str(os.getpid())


@pytest.mark.parametrize("junk", ["", "   ", "not-a-pid", "\x00"])
def test_unreadable_lock_is_treated_as_free(tmp_path, junk):
    wd = tmp_path / "work"
    wd.mkdir()
    (wd / _WORKDIR_LOCK_NAME).write_text(junk)
    claim_workdir(wd)  # must not raise


def test_release_removes_only_our_lock(tmp_path):
    wd = tmp_path / "work"
    claim_workdir(wd)
    release_workdir(wd)
    assert not (wd / _WORKDIR_LOCK_NAME).exists()

    (wd / _WORKDIR_LOCK_NAME).write_text("1")
    release_workdir(wd)
    assert (wd / _WORKDIR_LOCK_NAME).exists(), "must not steal another run's lock"


def test_release_is_safe_when_absent(tmp_path):
    release_workdir(tmp_path / "never-created")  # must not raise


class _FakeWinFunction:
    def __init__(self, callback):
        self.callback = callback
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.callback(*args)


class _FakeKernel32:
    def __init__(self, *, handle=123, exit_code=259, exit_query_ok=True):
        self.closed = []
        self.OpenProcess = _FakeWinFunction(lambda *_args: handle)

        def get_exit_code(_handle, output):
            output._obj.value = exit_code
            return exit_query_ok

        self.GetExitCodeProcess = _FakeWinFunction(get_exit_code)
        self.CloseHandle = _FakeWinFunction(lambda value: self.closed.append(value) or True)


def test_windows_pid_query_is_non_destructive_and_closes_handle():
    kernel32 = _FakeKernel32(exit_code=259)

    assert utils._windows_pid_is_alive(
        42, kernel32=kernel32, get_last_error=lambda: 0
    ) is True
    assert kernel32.closed == [123]


@pytest.mark.parametrize(
    ("last_error", "expected"),
    [(5, True), (87, False), (123, None)],
)
def test_windows_pid_query_classifies_open_errors(last_error, expected):
    kernel32 = _FakeKernel32(handle=0)

    assert utils._windows_pid_is_alive(
        42, kernel32=kernel32, get_last_error=lambda: last_error
    ) is expected
    assert kernel32.closed == []


def test_windows_pid_query_closes_handle_when_exit_query_fails():
    kernel32 = _FakeKernel32(exit_query_ok=False)

    assert utils._windows_pid_is_alive(
        42, kernel32=kernel32, get_last_error=lambda: 0
    ) is None
    assert kernel32.closed == [123]


@pytest.mark.parametrize(("alive", "expected_holder"), [(True, 42), (False, None), (None, 42)])
def test_lock_holder_fails_closed_when_liveness_is_unknown(
    tmp_path, monkeypatch, alive, expected_holder
):
    lock = tmp_path / _WORKDIR_LOCK_NAME
    lock.write_text("42")
    monkeypatch.setattr(utils, "_pid_is_alive", lambda _pid: alive)

    assert utils._lock_holder_pid(lock) == expected_holder


def test_windows_pid_dispatch_never_calls_os_kill(monkeypatch):
    monkeypatch.setattr(utils.os, "name", "nt")
    monkeypatch.setattr(utils, "_windows_pid_is_alive", lambda _pid: True)
    monkeypatch.setattr(
        utils.os,
        "kill",
        lambda *_args: pytest.fail("Windows liveness checks must not call os.kill"),
    )

    assert utils._pid_is_alive(42) is True


def _find_unused_pid() -> int:
    for pid in range(320000, 400000):
        if utils._pid_is_alive(pid) is False:
            return pid
    pytest.skip("no free PID found to simulate a stale lock")
