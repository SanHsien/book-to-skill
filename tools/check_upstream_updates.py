#!/usr/bin/env python3
"""Report upstream work that this fork has not reviewed yet.

CANONICAL COPY. This file lives in SanHsien/repo-fleet-ops
(``tools/canonical/check_upstream_updates.py``) and is copied verbatim into every fork as
``tools/check_upstream_updates.py``. Do not edit a fork's copy; change the canonical file,
extend its tests, and re-sync. ``python -m fleet_ops audit`` reports forks whose copy has
drifted. Per-fork differences belong in ``tools/upstream_baseline.json``, never in code.

Axes (each fails closed: "could not check" is never reported as "nothing new"):

* commits -- everything past ``reviewed_through``; ``track`` picks the granularity:
  ``commit`` (default) reads the upstream branch, ``release`` reads only the newest semver tag.
* pull requests / issues -- everything numbered above ``reviewed_pr_through`` /
  ``reviewed_issue_through``, closed ones included.
* branches (optional) -- ``branches`` lists registered names, ``reviewed_branch_heads`` maps a
  name to the head it was read at; anything else is reported.
* monitored (optional) -- ``monitored`` pins conditional verdicts ("revisit when X") to the head
  and state they were judged at, so advancing a watermark cannot silence them.
* website (optional) -- ``website`` serves ``version.json``; ``reviewed_website_version``.
  An unreachable site is "could not check" (exit 2), like every other axis.

Exit codes (the contract the workflows depend on; ``--strict`` only changes 0 into 1):

* 0 -- checked completely, nothing pending (or pending but not ``--strict``)
* 1 -- ``--strict`` and something is pending review
* 2 -- the check could not be completed: bad baseline, git/gh failure, a listing that hit its
  cap before reaching the watermark, or any unexpected crash. Never confused with 1.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BASELINE_PATH = SCRIPT_DIR / "upstream_baseline.json"
UPSTREAM_REF_PREFIX = "refs/upstream-check"
DEFAULT_DECISION_LOG = "docs/DECISIONS.md"
TRACK_MODES = ("release", "commit")
# `v1.7` is a release as much as `v1.7.0` (jev-chat-jarvis upstream); a missing patch reads as 0.
_SEMVER_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$")

# `gh pr|issue list` has no offset, only `--limit`. Start small and grow the limit until the
# listing reaches the reviewed watermark, so a fast-moving upstream is never silently truncated.
# If even the cap does not reach the watermark the scan is reported incomplete -- never as clean.
TICKET_LIMIT_START = 100
TICKET_LIMIT_CAP = 1000
# Every external call is bounded: a hung `git fetch` or `gh` must end as exit 2, not as a CI job
# that runs until the platform kills it.
GIT_TIMEOUT = 1200
GH_TIMEOUT = 180
HTTP_TIMEOUT = 20


class UpstreamCheckError(RuntimeError):
    """Raised when the baseline or upstream Git history cannot be inspected."""


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    if not path.is_file():
        raise UpstreamCheckError(f"missing baseline file: {path}")
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UpstreamCheckError(f"invalid baseline file: {path}: {exc}") from exc
    if not isinstance(baseline, dict):
        raise UpstreamCheckError(f"invalid baseline file: {path}: not a JSON object")
    required = {"repo", "branch", "reviewed_through", "reviewed_date"}
    missing = sorted(required - baseline.keys())
    if missing:
        raise UpstreamCheckError(f"baseline missing fields: {', '.join(missing)}")
    if len(str(baseline["reviewed_through"])) != 40:
        raise UpstreamCheckError("reviewed_through must be a full 40-character SHA")
    track = baseline.get("track", "commit")
    if track not in TRACK_MODES:
        raise UpstreamCheckError(f"track must be one of {', '.join(TRACK_MODES)}, not {track!r}")
    branches = baseline.get("branches")
    if branches is not None and not (
        isinstance(branches, list) and all(isinstance(name, str) for name in branches)
    ):
        raise UpstreamCheckError("branches must be a list of branch names")
    heads = baseline.get("reviewed_branch_heads")
    if heads is not None and not (
        isinstance(heads, dict) and all(isinstance(v, str) for v in heads.values())
    ):
        raise UpstreamCheckError("reviewed_branch_heads must map branch name to head SHA")
    monitored = baseline.get("monitored")
    if monitored is not None:
        if not isinstance(monitored, list):
            raise UpstreamCheckError("monitored must be a list")
        for entry in monitored:
            item = str(entry.get("item", "")) if isinstance(entry, dict) else ""
            number = item[3:]
            if not (item.startswith("pr#") and number.isascii() and number.isdigit()):
                raise UpstreamCheckError(f"monitored entries need item 'pr#<number>': {entry!r}")
    return baseline


def branch_axis_enabled(baseline: dict) -> bool:
    return "reviewed_branch_heads" in baseline or baseline.get("check_branches") is True


def parse_tag_refs(raw: str) -> list[tuple[tuple[int, int, int], str, str]]:
    """Parse ``git ls-remote --tags`` output into sorted (version, tag, sha)."""
    commits: dict[str, str] = {}
    for line in raw.splitlines():
        if "\t" not in line:
            continue
        sha, ref = line.split("\t", 1)
        name = ref.strip().removeprefix("refs/tags/")
        peeled = name.endswith("^{}")
        name = name.removesuffix("^{}")
        if not _SEMVER_TAG_RE.match(name):
            continue
        if peeled or name not in commits:
            commits[name] = sha.strip()

    parsed = []
    for name, sha in commits.items():
        match = _SEMVER_TAG_RE.match(name)
        if match is None:
            continue
        parts = tuple(int(part or 0) for part in match.groups())
        parsed.append((parts, name, sha))
    return sorted(parsed)


def _run(command: list[str], cwd: Path | None, timeout: int) -> subprocess.CompletedProcess:
    """Run a command; a missing executable or a hang surfaces as ``UpstreamCheckError``."""
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            # Titles, branch names and commit subjects are written by strangers and the console
            # is not always UTF-8; without this one undecodable byte kills the whole check.
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except OSError as exc:
        raise UpstreamCheckError(f"{command[0]} could not run: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise UpstreamCheckError(f"{' '.join(command[:3])} timed out after {timeout}s") from exc


def run_git(args: list[str], repo_dir: Path) -> str:
    result = _run(["git", *args], repo_dir, GIT_TIMEOUT)
    if result.returncode != 0:
        raise UpstreamCheckError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def run_gh(args: list[str]) -> subprocess.CompletedProcess | None:
    """``gh`` result, or ``None`` when it could not be run at all (missing, hung)."""
    try:
        return _run(["gh", *args], None, GH_TIMEOUT)
    except UpstreamCheckError:
        return None


def latest_upstream_release(baseline: dict, repo_dir: Path) -> tuple[str, str] | None:
    """Return the highest semver tag upstream publishes, as (tag, commit sha)."""
    tags = parse_tag_refs(run_git(["ls-remote", "--tags", baseline["repo"]], repo_dir))
    if not tags:
        return None
    _, name, sha = tags[-1]
    return name, sha


def fetch_upstream(baseline: dict, repo_dir: Path) -> str:
    branch = baseline["branch"]
    ref = f"{UPSTREAM_REF_PREFIX}/{branch}"
    run_git(["fetch", "--quiet", baseline["repo"], f"+refs/heads/{branch}:{ref}"], repo_dir)
    return ref


def fetch_upstream_release(baseline: dict, repo_dir: Path, tag: str) -> str:
    ref = f"{UPSTREAM_REF_PREFIX}/tags/{tag}"
    run_git(["fetch", "--quiet", baseline["repo"], f"+refs/tags/{tag}:{ref}"], repo_dir)
    return ref


def history_rewritten(reviewed: str, upstream_ref: str, repo_dir: Path) -> bool:
    """True when the reviewed commit is no longer part of upstream's history.

    A force-push upstream leaves ``reviewed_through`` unreachable; ``reviewed..ref`` would then
    list upstream's entire history as "new" -- a huge review queue instead of the one decision
    actually needed (re-anchor the baseline).
    """
    result = _run(
        ["git", "merge-base", "--is-ancestor", reviewed, upstream_ref], repo_dir, GIT_TIMEOUT
    )
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    raise UpstreamCheckError(
        f"git merge-base --is-ancestor {reviewed[:7]} failed: {result.stderr.strip()}"
    )


def shares_history(reviewed: str, repo_dir: Path) -> bool:
    """Does HEAD have any commit in common with the reviewed upstream commit?

    After a squash the fork has no common ancestor with upstream, and ``reviewed..HEAD`` would
    then count every fork commit as "ahead" -- a number that means nothing.
    """
    result = _run(["git", "merge-base", "HEAD", reviewed], repo_dir, GIT_TIMEOUT)
    if result.returncode == 0:
        return True
    if result.returncode == 1:  # git merge-base: exit 1 means "no common ancestor"
        return False
    raise UpstreamCheckError(f"git merge-base HEAD failed: {result.stderr.strip()}")


def fork_status(baseline: dict, repo_dir: Path, upstream_ref: str) -> dict:
    reviewed = baseline["reviewed_through"]

    def count(rev_range: str) -> int:
        return int(run_git(["rev-list", "--count", rev_range], repo_dir).strip())

    return {
        "baseline": reviewed[:7],
        "fork_head": run_git(["rev-parse", "--short", "HEAD"], repo_dir).strip(),
        "upstream_tip": run_git(["rev-parse", "--short", upstream_ref], repo_dir).strip(),
        "ahead": count(f"{reviewed}..HEAD") if shares_history(reviewed, repo_dir) else None,
        "behind": count(f"{reviewed}..{upstream_ref}"),
    }


def render_fork_status(status: dict | None, error: str | None = None) -> list[str]:
    if status is None:
        return ["## Fork status", "", f"無法計算：{error or 'unknown'}", ""]
    ahead = (
        f"baseline 之後 **ahead {status['ahead']}**"
        if status["ahead"] is not None
        else "與 upstream 無共同祖先（歷史已壓縮），不計 ahead"
    )
    return [
        "## Fork status",
        "",
        f"- 共同 baseline：`{status['baseline']}`（已審視至此）",
        f"- 本 fork `HEAD`：`{status['fork_head']}`，{ahead}",
        f"- upstream tip：`{status['upstream_tip']}`，baseline 之後 **behind {status['behind']}**",
        "",
        "這兩個數字每次 commit 都會變，所以由本檢查當場算出，不寫進文件。",
        "",
    ]


def collect_new_commits(baseline: dict, repo_dir: Path, ref: str) -> list[dict]:
    reviewed = baseline["reviewed_through"]
    raw = run_git(
        ["log", "--reverse", "--date=short", "--format=%H%x1f%ad%x1f%s", f"{reviewed}..{ref}"],
        repo_dir,
    )
    commits = []
    # `str.splitlines()` would also break on U+2028, U+0085 and form feed, all legal inside a
    # subject a stranger wrote; git ends each record with a plain newline.
    for line in raw.split("\n"):
        if not line.strip():
            continue
        sha, date, subject = line.split("\x1f", 2)
        files = [
            item
            for item in run_git(["show", "--name-only", "--format=", sha], repo_dir).splitlines()
            if item.strip()
        ]
        commits.append(
            {"sha": sha, "short": sha[:7], "date": date, "subject": subject, "files": files}
        )
    return commits


def upstream_slug(repo: str, repo_dir: Path | None = None) -> str | None:
    """`https://github.com/owner/name.git` -> `owner/name`, or None if not GitHub.

    A baseline may name a git *remote* (``upstream``) instead of a URL; that carries no owner or
    repository, so it is resolved through git first.
    """
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?/?$", repo)
    if match:
        return f"{match['owner']}/{match['name']}"
    if repo_dir is None or "/" in repo or ":" in repo:
        return None
    try:
        url = run_git(["remote", "get-url", repo], repo_dir).strip()
    except UpstreamCheckError:
        return None
    return upstream_slug(url) if url else None


@dataclass
class TicketScan:
    """Result of listing upstream PRs or issues past a watermark.

    ``complete`` is False when the listing hit ``limit`` without reaching the watermark: ``items``
    is then only the newest ``limit`` entries and older unreviewed ones may be missing.
    ``disabled`` marks an upstream that turned the ticket type off: a standing fact, reported as
    "not checked" but not a failure.
    """

    items: list[dict]
    complete: bool
    limit: int
    disabled: bool = False


def _list_tickets(slug: str, kind: str, limit: int) -> list[dict] | str | None:
    """The newest ``limit`` items; ``None`` when it could not be listed; ``"disabled"``."""
    result = run_gh(
        [kind, "list", "--repo", slug, "--state", "all", "--limit", str(limit)]
        + ["--json", "number,title"]
    )
    if result is None:
        return None
    if result.returncode != 0:
        stderr = result.stderr.lower()
        if "disabled issues" in stderr or "disabled pull requests" in stderr:
            return "disabled"
        return None
    try:
        items = json.loads(result.stdout)
    except ValueError:
        return None
    if not isinstance(items, list):
        return None
    if not all(isinstance(item, dict) and isinstance(item.get("number"), int) for item in items):
        return None
    return items


def collect_new_tickets(
    baseline: dict, kind: str, repo_dir: Path | None = None, cap: int = TICKET_LIMIT_CAP
) -> TicketScan | None:
    """List upstream items numbered above the watermark; ``None`` means "could not check"."""
    slug = upstream_slug(str(baseline["repo"]), repo_dir)
    if not slug:
        return None
    watermark = int(baseline.get(f"reviewed_{kind}_through", 0) or 0)
    limit = min(TICKET_LIMIT_START, cap)
    while True:
        items = _list_tickets(slug, kind, limit)
        if items is None:
            return None
        if items == "disabled":
            return TicketScan([], True, limit, disabled=True)
        assert isinstance(items, list)
        new = sorted(
            (item for item in items if item["number"] > watermark),
            key=lambda item: item["number"],
        )
        # `gh` lists newest first. The listing is complete once it ran out of items (fewer than
        # asked for) or already contains something at or below the watermark.
        if len(items) < limit or any(item["number"] <= watermark for item in items):
            return TicketScan(new, True, limit)
        if limit >= cap:
            return TicketScan(new, False, limit)
        limit = min(limit * 2, cap)


def collect_branch_changes(baseline: dict, repo_dir: Path) -> list[dict]:
    """Upstream branches, other than the tracked one, that are new or moved since review.

    The commit axis reads exactly one ref, so a branch pushed beside it (a release branch, a
    security backport) is otherwise invisible. A branch is reported when its name is not
    registered in ``branches``/``reviewed_branch_heads``, or when ``reviewed_branch_heads`` holds
    a different head for it.
    """
    heads = baseline.get("reviewed_branch_heads") or {}
    registered = set(baseline.get("branches") or []) | set(heads)
    raw = run_git(["ls-remote", "--heads", baseline["repo"]], repo_dir)
    changes = []
    seen = 0
    for line in raw.splitlines():
        if "\t" not in line:
            continue
        sha, ref = line.split("\t", 1)
        name = ref.strip().removeprefix("refs/heads/")
        seen += 1
        if name == baseline["branch"]:
            continue
        if name not in registered or (name in heads and heads[name] != sha):
            changes.append(
                {"name": name, "sha": sha, "short": sha[:7], "previous": heads.get(name)}
            )
    if seen == 0:
        # A public repo always has a head; an empty parse means the output was not what this
        # reader assumed, not that upstream has no branches.
        raise UpstreamCheckError("git ls-remote --heads returned no branches")
    return sorted(changes, key=lambda item: item["name"])


def collect_stale_monitored(baseline: dict, repo_dir: Path | None = None) -> list[dict] | None:
    """Monitored upstream PRs whose head SHA or open/draft/closed state has moved.

    Some verdicts are conditional ("reject for now, revisit when X"). They were reached by reading
    ONE diff, so they only hold while upstream's head is the one that was read. Advancing
    ``reviewed_pr_through`` past such a PR silences it forever, so each ``monitored`` entry pins
    ``item`` (``pr#N``), ``head`` and ``state`` (open|draft|closed) and drift is reported.
    ``None`` when ``gh`` could not answer.
    """
    declared = baseline.get("monitored") or []
    slug = upstream_slug(str(baseline["repo"]), repo_dir)
    if declared and not slug:
        return None
    stale: list[dict] = []
    for entry in declared:
        number = int(str(entry["item"])[3:])
        result = run_gh(
            ["pr", "view", str(number), "--repo", str(slug)]
            + ["--json", "state,isDraft,headRefOid"]
        )
        if result is None:
            return None
        if result.returncode != 0:
            if "could not resolve" in result.stderr.lower() or "not found" in result.stderr.lower():
                stale.append(
                    {"item": entry["item"], "was": entry.get("head", "?"), "now": "not found"}
                )
                continue
            return None
        try:
            current = json.loads(result.stdout)
            head = str(current["headRefOid"])
            state = "closed" if current["state"] != "OPEN" else "open"
            if state == "open" and current.get("isDraft"):
                state = "draft"
        except (ValueError, KeyError, TypeError):
            return None
        pinned = str(entry.get("head", ""))
        # Compare on the shorter of the two so a 7-char pin matches a full SHA -- but an empty or
        # too-short pin is drift, not a match.
        length = min(len(pinned), len(head))
        moved = not pinned or length < 7 or pinned[:length] != head[:length]
        if moved or state != entry.get("state"):
            stale.append(
                {
                    "item": entry["item"],
                    "was": f"{pinned or '(none)'} / {entry.get('state', '(none)')}",
                    "now": f"{head[:7]} / {state}",
                }
            )
    return stale


def check_upstream_website(baseline: dict) -> dict | None:
    """``version.json`` of the upstream documentation website, when the baseline names one."""
    website = baseline.get("website")
    if not website:
        return None
    url = f"{str(website).rstrip('/')}/version.json"
    reviewed = str(baseline.get("reviewed_website_version", "")).strip()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "fleet-upstream-check/1"})
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            if response.status != 200:
                return {"url": website, "error": f"HTTP {response.status}"}
            data = json.loads(response.read().decode("utf-8"))
        return {
            "url": website,
            "current": str(data.get("version", "")).strip(),
            "reviewed": reviewed,
        }
    except Exception as exc:  # network, TLS, JSON: all mean "could not read", never "unchanged"
        return {"url": website, "error": str(exc)}


def _cell(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def render_ticket_section(
    title: str, watermark: int, scan: TicketScan | None, kind: str, decision_log: str
) -> list[str]:
    lines = [f"## {title}", "", f"Triaged through `#{watermark}`.", ""]
    if scan is None:
        lines.extend(
            [
                "Not checked: `gh` was unavailable, unauthenticated, or the baseline",
                "does not name a GitHub repository. Reported as such rather than as",
                '"nothing to review" -- the difference matters.',
                "",
            ]
        )
        return lines
    if scan.disabled:
        lines.extend(
            [
                "Not checked: the upstream repository has this ticket type disabled. That is a",
                "standing fact about upstream, not a failed check, and it is reported as",
                '"not checked" rather than "no new items" -- the difference matters.',
                "",
            ]
        )
        return lines
    tickets = scan.items
    if not tickets and scan.complete:
        lines.extend(["No new items above that number.", ""])
        return lines
    if scan.complete:
        lines.extend([f"{len(tickets)} new item(s) to triage.", ""])
    else:
        lines.extend(
            [
                f"**INCOMPLETE:** `gh` returned its maximum of {scan.limit} items without",
                f"reaching `#{watermark}`. The {len(tickets)} item(s) below are only the newest;",
                "older unreviewed ones may be missing. This is NOT a full list -- triage",
                "the rest directly on GitHub, or raise the watermark in steps.",
                "",
            ]
        )
    if tickets:
        lines.extend(["| Item | Title |", "| --- | --- |"])
        lines.extend(
            f"| #{ticket['number']} | {_cell(ticket.get('title', ''))} |" for ticket in tickets
        )
        lines.append("")
    lines.extend(
        [
            f"Record the verdict in `{decision_log}`, then raise",
            f"`reviewed_{kind}_through` so the same item is never re-triaged.",
            "",
        ]
    )
    return lines


def render_branch_section(changes: list[dict], baseline: dict, decision_log: str) -> list[str]:
    known = ", ".join(
        f"`{name}`"
        for name in sorted(
            set(baseline.get("branches") or []) | set(baseline.get("reviewed_branch_heads") or {})
        )
    )
    lines = ["## Upstream branches", "", f"Registered: {known or '(none)'}.", ""]
    if not changes:
        return [*lines, "No branches beyond, or moved since, the registered ones.", ""]
    lines.extend([f"{len(changes)} branch(es) to triage.", "", "| Branch | Head | Previously |"])
    lines.append("| --- | --- | --- |")
    for change in changes:
        previous = f"`{change['previous'][:7]}`" if change["previous"] else "(new)"
        lines.append(f"| `{_cell(change['name'])}` | `{change['short']}` | {previous} |")
    lines.extend(
        [
            "",
            f"Record the verdict in `{decision_log}`, then register the branch (and head) in",
            "`branches` / `reviewed_branch_heads` in `tools/upstream_baseline.json`.",
            "",
        ]
    )
    return lines


def render_monitored_section(
    baseline: dict, stale: list[dict] | None, decision_log: str
) -> list[str]:
    lines = [
        "## Monitored upstream items (conditional verdicts)",
        "",
        f"Pinned: {len(baseline.get('monitored') or [])}.",
        "",
    ]
    if stale is None:
        return [
            *lines,
            "Not checked: `gh` could not read the pinned pull requests. Reported as such",
            'rather than as "nothing moved" -- the difference matters.',
            "",
        ]
    if not stale:
        return [*lines, "Every pinned item is still at the head and state it was judged at.", ""]
    lines.extend(
        [
            f"{len(stale)} pinned item(s) moved since the verdict was recorded.",
            "",
            "| Item | Judged at | Now |",
            "| --- | --- | --- |",
        ]
    )
    lines.extend(f"| {e['item']} | `{e['was']}` | `{e['now']}` |" for e in stale)
    lines.extend(
        [
            "",
            f"Re-read the diff, update the verdict in `{decision_log}`, then re-pin",
            "`head`/`state` in `monitored` in `tools/upstream_baseline.json`.",
            "",
        ]
    )
    return lines


def render_website_section(info: dict) -> list[str]:
    lines = ["## Upstream documentation website", "", f"- Website: `{info['url']}`"]
    if "error" in info:
        return [*lines, f"- Not checked: {info['error']}", ""]
    if info["current"] != info["reviewed"]:
        return [
            *lines,
            f"- Version changed from `{info['reviewed']}` to `{info['current']}`; review the docs.",
            "",
        ]
    return [*lines, "- Documentation website: up to date.", ""]


def render_markdown(
    baseline: dict,
    commits: list[dict],
    error: str | None = None,
    release: str | None = None,
    status: dict | None = None,
    status_error: str | None = None,
) -> str:
    decision_log = baseline.get("decision_log", DEFAULT_DECISION_LOG)
    track = baseline.get("track", "commit")
    lines = [
        "# Upstream review report",
        "",
        f"- Upstream: `{baseline['repo']}` (`{baseline['branch']}`)",
        f"- Tracking: {track}",
        f"- Reviewed through: `{baseline['reviewed_through'][:7]}`"
        + (f" ({baseline['reviewed_release']})" if baseline.get("reviewed_release") else ""),
        f"- Last review date: {baseline['reviewed_date']}",
        "",
    ]
    if error:
        lines.extend(["## Check failed", "", f"```text\n{error}\n```", ""])
        return "\n".join(lines)
    if not commits:
        clean = (
            "No upstream release past the reviewed one. Nothing to review."
            if track == "release"
            else "No new upstream commits. Nothing to review."
        )
        lines.extend(["## Result", "", clean, ""])
        lines.extend(render_fork_status(status, status_error))
        return "\n".join(lines)

    headline = (
        f"Upstream released {release}: {len(commits)} commit(s) require review."
        if track == "release" and release
        else f"{len(commits)} upstream commit(s) require review."
    )
    lines.extend(
        [
            "## Result",
            "",
            headline,
            "",
            "| Commit | Date | Subject | Files |",
            "| --- | --- | --- | --- |",
        ]
    )
    for commit in commits:
        files = "<br>".join(_cell(item) for item in commit["files"][:8])
        if len(commit["files"]) > 8:
            files += f"<br>… +{len(commit['files']) - 8} more"
        lines.append(
            f"| `{commit['short']}` | {commit['date']} | {_cell(commit['subject'])} "
            f"| {files or '(none)'} |"
        )
    lines.extend(
        [
            "",
            f"Review each commit, record adopt/skip decisions in `{decision_log}`,",
            "then advance `tools/upstream_baseline.json` only after verification.",
            "",
        ]
    )
    lines.extend(render_fork_status(status, status_error))
    return "\n".join(lines)


def emit(text: str, stream: TextIO | None = None) -> None:
    """Print without depending on the console encoding.

    The report holds arbitrary upstream titles; a console that cannot encode one (cp950 on
    Traditional-Chinese Windows has no emoji, cp1252 has no CJK) must not abort the run, because
    a crash after the report file is written exits 1 and reads as "review needed". Unencodable
    characters are shown as escapes. The report file is always written as UTF-8 and stays exact.
    """
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="backslashreplace").decode(encoding), file=stream)


@dataclass
class Findings:
    """Everything one run learned. ``None`` in a field means that axis could not be checked."""

    baseline: dict
    commits: list[dict]
    release: str | None = None
    prs: TicketScan | None = None
    issues: TicketScan | None = None
    branches: list[dict] | None = None
    monitored: list[dict] | None = None
    website: dict | None = None
    status: dict | None = None
    status_error: str | None = None
    error: str | None = None


def gather(args: argparse.Namespace) -> Findings:
    repo_dir: Path = args.repo_dir
    try:
        baseline = load_baseline(args.baseline)
    except UpstreamCheckError as exc:
        placeholder = {
            "repo": "unknown",
            "branch": "unknown",
            "reviewed_through": "0" * 40,
            "reviewed_date": "unknown",
        }
        return Findings(placeholder, [], error=str(exc))

    findings = Findings(baseline, [])
    try:
        branch_ref = fetch_upstream(baseline, repo_dir)
        if history_rewritten(baseline["reviewed_through"], branch_ref, repo_dir):
            raise UpstreamCheckError(
                f"upstream rewrote its history: {baseline['reviewed_through'][:7]} is no longer "
                f"reachable from upstream {baseline['branch']}. Re-anchor reviewed_through on the "
                "upstream commit with the same tree before reviewing anything."
            )
        if baseline.get("track", "commit") == "release":
            newest = latest_upstream_release(baseline, repo_dir)
            if newest is None:
                raise UpstreamCheckError("upstream publishes no semver tags to track")
            tag, sha = newest
            if sha != baseline["reviewed_through"]:
                findings.release = tag
                ref = fetch_upstream_release(baseline, repo_dir, tag)
                findings.commits = collect_new_commits(baseline, repo_dir, ref)
        else:
            findings.commits = collect_new_commits(baseline, repo_dir, branch_ref)
        findings.prs = collect_new_tickets(baseline, "pr", repo_dir, args.ticket_cap)
        findings.issues = collect_new_tickets(baseline, "issue", repo_dir, args.ticket_cap)
        if branch_axis_enabled(baseline):
            findings.branches = collect_branch_changes(baseline, repo_dir)
        if "monitored" in baseline:
            findings.monitored = collect_stale_monitored(baseline, repo_dir)
        findings.website = check_upstream_website(baseline)
    except UpstreamCheckError as exc:
        findings.error = str(exc)
        return findings

    try:
        findings.status = fork_status(baseline, repo_dir, branch_ref)
    except UpstreamCheckError as exc:
        findings.status_error = str(exc)
    return findings


def build_report(findings: Findings) -> str:
    baseline = findings.baseline
    report = render_markdown(
        baseline,
        findings.commits,
        findings.error,
        findings.release,
        findings.status,
        findings.status_error,
    )
    if findings.error:
        return report
    log = baseline.get("decision_log", DEFAULT_DECISION_LOG)
    lines = [report.rstrip("\n"), ""]
    lines += render_ticket_section(
        "Upstream pull requests",
        int(baseline.get("reviewed_pr_through", 0) or 0),
        findings.prs,
        "pr",
        log,
    )
    lines += render_ticket_section(
        "Upstream issues",
        int(baseline.get("reviewed_issue_through", 0) or 0),
        findings.issues,
        "issue",
        log,
    )
    if branch_axis_enabled(baseline):
        lines += render_branch_section(findings.branches or [], baseline, log)
    if "monitored" in baseline:
        lines += render_monitored_section(baseline, findings.monitored, log)
    if findings.website is not None:
        lines += render_website_section(findings.website)
    return "\n".join(lines)


def unchecked_axes(findings: Findings) -> list[str]:
    """Axes that were asked for but could not be answered. Always exit 2, never exit 0 or 1."""
    baseline = findings.baseline
    missing = []
    if findings.prs is None:
        missing.append("pull requests")
    if findings.issues is None:
        missing.append("issues")
    if "monitored" in baseline and findings.monitored is None:
        missing.append("monitored pull requests")
    if findings.website is not None and "error" in findings.website:
        missing.append("the documentation website")
    return missing


def pending(findings: Findings) -> bool:
    website = findings.website
    website_changed = bool(
        website and "error" not in website and website["current"] != website["reviewed"]
    )
    return bool(
        findings.commits
        or (findings.prs and findings.prs.items)
        or (findings.issues and findings.issues.items)
        or findings.branches
        or findings.monitored
        or website_changed
    )


def exit_code(findings: Findings, strict: bool) -> tuple[int, str | None]:
    """The exit-code contract: 2 = could not complete, 1 = ``--strict`` and pending, else 0."""
    if findings.error:
        return 2, None
    missing = unchecked_axes(findings)
    if missing:
        return 2, "ERROR: could not enumerate upstream " + " and ".join(missing) + "."
    incomplete = [
        name
        for name, scan in (("pull requests", findings.prs), ("issues", findings.issues))
        if scan is not None and not scan.complete
    ]
    if incomplete:
        return 2, (
            "ERROR: the listing of upstream "
            + " and ".join(incomplete)
            + " hit its item cap before reaching the reviewed watermark; "
            "older unreviewed items may be missing."
        )
    if strict and pending(findings):
        return 1, None
    return 0, None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", default="upstream-review-report.md")
    parser.add_argument("--repo-dir", type=Path, default=REPO_ROOT)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument(
        "--ticket-cap",
        type=int,
        default=TICKET_LIMIT_CAP,
        help="Largest listing asked of gh before the scan is reported INCOMPLETE.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return 1 when something requires review (2 still means the check failed).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        findings = gather(args)
        report = build_report(findings)
        Path(args.output).write_text(report, encoding="utf-8")
        emit(report)
        code, message = exit_code(findings, args.strict)
        if message:
            emit(message)
        return code
    except Exception as exc:
        # An uncaught exception would exit 1 -- the same code as "review needed". Contract: 2.
        emit(f"ERROR: upstream check crashed: {type(exc).__name__}: {exc}", sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
