"""Builds a real GitHub test repository with open PRs made from samples/prs.json.

Use it to try PRTriage's "paste a repo link" mode against real pull requests that you control.
All content is synthetic (a fictional library called tinydate), so nothing private is involved.

    # See what would be created, locally, with no network and no token:
    python scripts/create_test_repo.py --dry-run

    # Create it on GitHub (public repo, needed for repo mode):
    $env:GITHUB_WRITE_TOKEN = "..."        # PowerShell. A token that may create repositories and pull requests.
    python scripts/create_test_repo.py --name tinydate-demo

GITHUB_WRITE_TOKEN is separate from the read-only GITHUB_TOKEN the app uses. Create it at
https://github.com/settings/tokens (classic token with the "public_repo" scope is enough), use it once and delete it.

Notes: the PR diffs are rebuilt from each sample's added lines, so on GitHub they look similar but not identical to the
samples. Sample 7 (no CONTRIBUTING.md) cannot be shown in the same repo as the others, so the repo has a CONTRIBUTING.md
and sample 7 appears as an ordinary small PR.
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.samples import load_samples  # noqa: E402

BASE_FILES = {
    "README.md": "# tinydate\n\nA tiny date parsing library. (Synthetic demo repository for PRTriage.)\n",
    "CONTRIBUTING.md": (
        "# Contributing to tinydate\n"
        "- One focused change per PR.\n"
        "- Bug fixes and new features must include tests.\n"
        "- Describe what and why in the PR description.\n"
        "- No debug output (print statements) in library code.\n"
        "- Run `pytest` before opening the PR.\n"
    ),
    "tinydate/__init__.py": "",
    "tinydate/parser.py": (
        "import re\nfrom datetime import date\n\n\n"
        "def parse_date(text):\n"
        '    """Parse YYYY-MM-DD into a date. Raises ValueError on bad input."""\n'
        '    parts = text.strip().split("-")\n'
        "    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])\n"
        "    return date(year, month, day)\n\n\n"
        "def format_date(d):\n"
        '    return d.strftime("%Y-%m-%d")\n'
    ),
    "tests/test_parser.py": (
        "from datetime import date\n\nfrom tinydate.parser import parse_date\n\n\n"
        "def test_valid_date():\n"
        '    assert parse_date("2024-02-29") == date(2024, 2, 29)\n'
    ),
}


def split_diff(diff: str) -> dict[str, list[list[str]]]:
    """Splits a unified diff into {path: [hunk_lines, ...]}. Hunk lines keep their +, - or space prefix."""
    files: dict[str, list[list[str]]] = {}
    path, hunk = None, None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[1].strip() if " b/" in line else None
            hunk = None
            if path:
                files.setdefault(path, [])
        elif path is None:
            continue
        elif line.startswith("@@"):
            hunk = []
            files[path].append(hunk)
        elif line.startswith(("--- ", "+++ ", "new file mode", "index ")):
            continue
        elif hunk is not None and line[:1] in ("+", "-", " "):
            hunk.append(line)
    return files


def apply_diff(workdir: Path, diff: str) -> list[str]:
    """Applies the changes of a (possibly hand-written) diff. A hunk whose old lines are found in the file is
    replaced in place; otherwise its added lines are appended. Returns the changed paths."""
    changed = []
    for rel, hunks in split_diff(diff).items():
        target = workdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        text = target.read_text(encoding="utf-8") if target.exists() else ""
        lines = text.splitlines()
        for hunk in hunks:
            old = [l[1:] for l in hunk if l[0] in " -"]
            new = [l[1:] for l in hunk if l[0] in " +"]
            at = _find(lines, old) if old else -1
            if at >= 0:
                lines[at:at + len(old)] = new
            else:
                lines.extend(l[1:] for l in hunk if l[0] == "+")
        target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        changed.append(rel)
    return changed


def _find(haystack: list[str], needle: list[str]) -> int:
    for i in range(len(haystack) - len(needle) + 1):
        if haystack[i:i + len(needle)] == needle:
            return i
    return -1


def git(cwd: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-c", "user.name=PRTriage Demo", "-c", "user.email=demo@example.invalid", *args],
                       cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout


def build_local_repo(workdir: Path, samples: list[dict]) -> list[dict]:
    git(workdir, "init", "-q", "-b", "main")
    for rel, content in BASE_FILES.items():
        p = workdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    git(workdir, "add", "-A")
    git(workdir, "commit", "-q", "-m", "Initial commit: tinydate")

    prs = []
    for s in samples:
        branch = f"pr-{s['id']}"
        git(workdir, "checkout", "-q", "-b", branch, "main")
        changed = apply_diff(workdir, s["diff"])
        git(workdir, "add", "-A")
        if not git(workdir, "status", "--porcelain").strip():
            git(workdir, "checkout", "-q", "main")
            print(f"  skipped {s['id']}: the diff changed nothing")
            continue
        git(workdir, "commit", "-q", "-m", s["title"])
        git(workdir, "checkout", "-q", "main")
        prs.append({"branch": branch, "title": s["title"], "body": s["body"] or "", "files": changed})
        print(f"  built {branch}: {s['title']}  ({', '.join(changed)})")
    return prs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="tinydate-demo", help="repository name to create")
    ap.add_argument("--dry-run", action="store_true", help="build locally only; no network, no token")
    args = ap.parse_args()

    samples = load_samples(ROOT / "samples" / "prs.json")
    token = os.getenv("GITHUB_WRITE_TOKEN", "")
    if not args.dry_run and not token:
        raise SystemExit("Set GITHUB_WRITE_TOKEN first (see the top of this file), or use --dry-run.")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        print("Building the local repo...")
        prs = build_local_repo(work, samples)
        if args.dry_run:
            print(f"\nDry run OK: {len(prs)} PR branches built. Nothing was sent to GitHub.")
            return

        api = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "prtriage-demo"}
        with httpx.Client(timeout=30, headers=api) as c:
            r = c.post("https://api.github.com/user/repos", json={
                "name": args.name, "private": False, "auto_init": False,
                "description": "Synthetic demo repository for testing PRTriage"})
            if r.status_code == 422:
                raise SystemExit(f"Could not create '{args.name}' (does it already exist? pick another --name).")
            r.raise_for_status()
            full = r.json()["full_name"]
            print(f"Created https://github.com/{full}")

            basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            header = f"http.extraheader=Authorization: Basic {basic}"  # keeps the token out of the URL and the remote
            remote = f"https://github.com/{full}.git"
            git(work, "remote", "add", "origin", remote)
            git(work, "-c", header, "push", "-q", "origin", "main", *[p["branch"] for p in prs])

            for p in prs:
                pr = c.post(f"https://api.github.com/repos/{full}/pulls",
                            json={"title": p["title"], "body": p["body"], "head": p["branch"], "base": "main"})
                if pr.status_code >= 300:
                    print(f"  could not open PR for {p['branch']}: HTTP {pr.status_code} {pr.text[:200]}")
                else:
                    print(f"  opened {pr.json()['html_url']}")
        print(f"\nDone. In PRTriage, paste: https://github.com/{full}  then press Load PRs.")
        print("Now delete the GITHUB_WRITE_TOKEN you used.")


if __name__ == "__main__":
    main()
