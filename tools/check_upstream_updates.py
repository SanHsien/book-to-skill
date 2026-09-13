"""Report upstream commits, pull requests, and issues this fork has not reviewed.

Commits are only one of the places upstream work shows up. A pull request can sit
open for months with a fix in it, and an issue can describe a defect this fork also
has -- neither reaches the commit log until somebody merges it. Each axis therefore
carries its own watermark, and the report only lists what is above it.

Tickets are queried with ``--state all`` on purpose: an item opened and closed
between two scheduled runs is still an item this fork never triaged, and a pull
request closed without merging never arrives on the commit axis at all.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tools" / "upstream_baseline.json"
UPSTREAM_REF_PREFIX = "refs/upstream-check"
DEFAULT_DECISION_LOG = "docs/DECISIONS.md"


class UpstreamCheckError(RuntimeError):
    """Raised when the baseline or upstream Git history cannot be inspected."""


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    if not path.is_file():
        raise UpstreamCheckError(f"missing baseline file: {path}")
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpstreamCheckError(f"invalid baseline file: {path}: {exc}") from exc
    required = {"repo", "branch", "reviewed_through", "reviewed_date"}
    missing = sorted(required - baseline.keys())
    if missing:
        raise UpstreamCheckError(f"baseline missing fields: {', '.join(missing)}")
    if len(baseline["reviewed_through"]) != 40:
        raise UpstreamCheckError("reviewed_through must be a full 40-character SHA")
    return baseline


def run_git(args: list[str], repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise UpstreamCheckError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout


def fetch_upstream(baseline: dict, repo_dir: Path) -> str:
    branch = baseline["branch"]
    ref = f"{UPSTREAM_REF_PREFIX}/{branch}"
    run_git(
        [
            "fetch",
            "--quiet",
            baseline["repo"],
            f"+refs/heads/{branch}:{ref}",
        ],
        repo_dir,
    )
    return ref


def collect_new_commits(baseline: dict, repo_dir: Path, ref: str) -> list[dict]:
    reviewed = baseline["reviewed_through"]
    raw = run_git(
        [
            "log",
            "--reverse",
            "--date=short",
            "--format=%H%x1f%ad%x1f%s",
            f"{reviewed}..{ref}",
        ],
        repo_dir,
    )
    commits = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, date, subject = line.split("\x1f", 2)
        files = [
            item
            for item in run_git(
                ["show", "--name-only", "--format=", sha], repo_dir
            ).splitlines()
            if item.strip()
        ]
        commits.append(
            {
                "sha": sha,
                "short": sha[:7],
                "date": date,
                "subject": subject,
                "files": files,
            }
        )
    return commits


def upstream_slug(repo_url: str) -> str | None:
    """`https://github.com/owner/name.git` -> `owner/name`, or None if not GitHub."""
    match = re.search(
        r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?$", repo_url
    )
    return f"{match['owner']}/{match['name']}" if match else None


def collect_new_tickets(baseline: dict, kind: str) -> list[dict] | None:
    """All PRs or issues numbered above the watermark, closed ones included.

    Returns ``None`` -- not an empty list -- when ``gh`` cannot answer, and the
    report says so. "Not checked" and "nothing to review" look identical in a
    green report, and only one of them is true; conflating them is how a fork
    stops noticing upstream without anybody deciding to.
    """
    slug = upstream_slug(str(baseline["repo"]))
    if not slug:
        return None
    watermark = int(baseline.get(f"reviewed_{kind}_through", 0) or 0)
    result = subprocess.run(
        [
            "gh", kind, "list", "--repo", slug, "--state", "all",
            "--limit", "1000", "--json", "number,title",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        # `errors` is not optional here. Ticket titles are written by strangers
        # and the console this runs on is not always UTF-8; without it a single
        # undecodable byte raises UnicodeDecodeError and the whole upstream
        # check dies instead of reporting the tickets it did read.
        errors="replace",
    )
    if result.returncode != 0:
        return None
    try:
        items = json.loads(result.stdout)
    except ValueError:
        return None
    return sorted(
        (item for item in items if item["number"] > watermark),
        key=lambda item: item["number"],
    )


def render_ticket_section(
    title: str,
    watermark: int,
    tickets: list[dict] | None,
    kind: str,
    decision_log: str,
) -> list[str]:
    lines = [f"## {title}", "", f"Triaged through `#{watermark}`.", ""]
    if tickets is None:
        lines.extend(
            [
                "Not checked: `gh` was unavailable, unauthenticated, or the baseline",
                "does not name a GitHub repository. Reported as such rather than as",
                '"nothing to review" -- the difference matters.',
                "",
            ]
        )
        return lines
    if not tickets:
        lines.extend(["No new items above that number.", ""])
        return lines
    lines.extend(
        [
            f"{len(tickets)} new item(s) to triage.",
            "",
            "| Item | Title |",
            "| --- | --- |",
        ]
    )
    for ticket in tickets:
        # The escape is computed outside the f-string: a backslash inside an
        # f-string expression is a SyntaxError before Python 3.12.
        item_title = ticket["title"].replace("|", "\\|")
        lines.append(f"| #{ticket['number']} | {item_title} |")
    lines.extend(
        [
            "",
            f"Record the verdict in `{decision_log}`, then raise",
            f"`reviewed_{kind}_through` so the same item is never re-triaged.",
            "",
        ]
    )
    return lines


def render_markdown(
    baseline: dict,
    commits: list[dict],
    prs: list[dict] | None = None,
    issues: list[dict] | None = None,
    error: str | None = None,
) -> str:
    decision_log = baseline.get("decision_log", DEFAULT_DECISION_LOG)
    lines = [
        "# Upstream review report",
        "",
        f"- Upstream: `{baseline['repo']}` (`{baseline['branch']}`)",
        f"- Reviewed through: `{baseline['reviewed_through'][:7]}`",
        f"- Last review date: {baseline['reviewed_date']}",
        "",
    ]
    if error:
        lines.extend(["## Check failed", "", f"```text\n{error}\n```", ""])
        return "\n".join(lines)

    def with_tickets(body: list[str]) -> str:
        body = body + render_ticket_section(
            "Upstream pull requests",
            int(baseline.get("reviewed_pr_through", 0) or 0),
            prs,
            "pr",
            decision_log,
        )
        body += render_ticket_section(
            "Upstream issues",
            int(baseline.get("reviewed_issue_through", 0) or 0),
            issues,
            "issue",
            decision_log,
        )
        return "\n".join(body)

    if not commits:
        lines.extend(
            ["## Commits", "", "No new upstream commits. Nothing to review.", ""]
        )
        return with_tickets(lines)

    lines.extend(
        [
            "## Commits",
            "",
            f"{len(commits)} upstream commit(s) require review.",
            "",
            "| Commit | Date | Subject | Files |",
            "| --- | --- | --- | --- |",
        ]
    )
    for commit in commits:
        subject = commit["subject"].replace("|", "\\|")
        files = "<br>".join(item.replace("|", "\\|") for item in commit["files"][:8])
        if len(commit["files"]) > 8:
            files += f"<br>… +{len(commit['files']) - 8} more"
        lines.append(
            f"| `{commit['short']}` | {commit['date']} | {subject} | {files or '(none)'} |"
        )
    lines.extend(
        [
            "",
            f"Review each commit, record adopt/skip decisions in `{decision_log}`, ",
            "then advance `tools/upstream_baseline.json` only after verification.",
            "",
        ]
    )
    return with_tickets(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="upstream-review-report.md")
    parser.add_argument("--repo-dir", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when new commits, pull requests, or issues need review.",
    )
    args = parser.parse_args()

    baseline: dict
    commits: list[dict] = []
    prs: list[dict] | None = None
    issues: list[dict] | None = None
    error: str | None = None
    try:
        baseline = load_baseline()
        ref = fetch_upstream(baseline, args.repo_dir)
        commits = collect_new_commits(baseline, args.repo_dir, ref)
        prs = collect_new_tickets(baseline, "pr")
        issues = collect_new_tickets(baseline, "issue")
    except UpstreamCheckError as exc:
        error = str(exc)
        baseline = {
            "repo": "unknown",
            "branch": "unknown",
            "reviewed_through": "0" * 40,
            "reviewed_date": "unknown",
        }

    report = render_markdown(baseline, commits, prs, issues, error)
    output = Path(args.output)
    output.write_text(report, encoding="utf-8")
    print(report)

    if error:
        return 2
    unavailable = [
        name
        for name, value in (("pull requests", prs), ("issues", issues))
        if value is None
    ]
    if unavailable:
        # Fail closed. A report that could not enumerate tickets must not be
        # allowed to read as a clean bill of health.
        print(f"ERROR: gh could not enumerate upstream {' and '.join(unavailable)}.")
        return 2
    if args.strict and (commits or prs or issues):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
