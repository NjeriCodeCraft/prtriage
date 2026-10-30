"""Fetches a public pull request from GitHub. Read-only, public data only."""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from . import config

PR_URL = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)/?(?:[#?].*)?$")
REPO_URL = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?].*)?$")

# CONTRIBUTING.md rarely changes during a session; caching it saves GitHub rate limit when triaging many PRs.
_CONTRIB_CACHE: dict[tuple[str, str], str | None] = {}


class GitHubError(Exception):
    pass


@dataclass
class PullRequest:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    diff: str
    contributing: str | None
    author_account_age_days: int | None  # weak signal, displayed only, NEVER sent to Gemma


def parse_pr_url(url: str) -> tuple[str, str, int]:
    m = PR_URL.match(url.strip())
    if not m:
        raise GitHubError("That doesn't look like a GitHub pull request URL (https://github.com/OWNER/REPO/pull/NUMBER).")
    return m.group(1), m.group(2), int(m.group(3))


def _headers(accept: str) -> dict[str, str]:
    h = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "prtriage"}
    if config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return h


def _get(client: httpx.Client, url: str, accept: str) -> httpx.Response:
    try:
        return client.get(url, headers=_headers(accept))
    except httpx.HTTPError as exc:
        raise GitHubError(f"Could not reach GitHub: {exc}") from exc


def fetch_pr(url: str) -> PullRequest:
    from datetime import datetime, timezone

    owner, repo, number = parse_pr_url(url)
    base = f"https://api.github.com/repos/{owner}/{repo}"
    with httpx.Client(timeout=20) as client:
        meta = _get(client, f"{base}/pulls/{number}", "application/vnd.github+json")
        if meta.status_code == 404:
            raise GitHubError("Pull request not found (is the repository public?).")
        if meta.status_code in (403, 429):
            raise GitHubError("GitHub rate limit reached. Set GITHUB_TOKEN or use the paste mode.")
        if meta.status_code != 200:
            raise GitHubError(f"GitHub returned HTTP {meta.status_code}.")
        data = meta.json()

        diff_resp = _get(client, f"{base}/pulls/{number}", "application/vnd.github.v3.diff")
        diff = diff_resp.text if diff_resp.status_code == 200 else ""

        key = (owner.lower(), repo.lower())
        if key in _CONTRIB_CACHE:
            contributing = _CONTRIB_CACHE[key]
        else:
            contributing, statuses = None, []
            for path in ("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"):
                r = _get(client, f"{base}/contents/{path}", "application/vnd.github.raw+json")
                statuses.append(r.status_code)
                if r.status_code == 200:
                    contributing = r.text
                    break
            if contributing or all(s == 404 for s in statuses):  # never cache a rate-limit failure
                _CONTRIB_CACHE[key] = contributing

        age = None
        login = (data.get("user") or {}).get("login")
        if login:
            u = _get(client, f"https://api.github.com/users/{login}", "application/vnd.github+json")
            if u.status_code == 200 and u.json().get("created_at"):
                created = datetime.fromisoformat(u.json()["created_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - created).days

    return PullRequest(owner, repo, number, data.get("title") or "", data.get("body") or "", diff, contributing, age)


def parse_repo_url(url: str) -> tuple[str, str]:
    """Accepts a repo link, or a PR link (the repo is taken from it)."""
    m = REPO_URL.match(url.strip())
    if not m:
        raise GitHubError("That doesn't look like a GitHub repository link (https://github.com/OWNER/REPO).")
    return m.group(1), m.group(2)


def list_open_prs(url: str, limit: int = 20) -> dict:
    """Lists the most recently updated open PRs of a public repo. Authors are deliberately left out."""
    owner, repo = parse_repo_url(url)
    api = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&sort=updated&direction=desc&per_page={limit}"
    with httpx.Client(timeout=20) as client:
        r = _get(client, api, "application/vnd.github+json")
    if r.status_code == 404:
        raise GitHubError("Repository not found. Check the link, and that the repository is public.")
    if r.status_code in (403, 429):
        raise GitHubError("GitHub rate limit reached. Add a GITHUB_TOKEN on the server, or use the demo PRs.")
    if r.status_code != 200:
        raise GitHubError(f"GitHub returned HTTP {r.status_code}.")
    prs = [
        {"number": p["number"], "title": p.get("title") or "", "url": p["html_url"],
         "draft": bool(p.get("draft")), "updated_at": p.get("updated_at")}
        for p in r.json()
    ]
    return {"owner": owner, "repo": repo, "prs": prs}
