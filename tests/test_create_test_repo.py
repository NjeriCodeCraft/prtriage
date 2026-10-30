"""Checks the local half of scripts/create_test_repo.py (no network, no token)."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import create_test_repo as ctr  # noqa: E402
from app.samples import load_samples  # noqa: E402


def test_split_diff_and_apply_in_place(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n")
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n x = 1\n-y = 2\n+y = 20\n z = 3\n"
    assert ctr.split_diff(diff)["a.py"][0][1] == "-y = 2"
    assert ctr.apply_diff(tmp_path, diff) == ["a.py"]
    assert (tmp_path / "a.py").read_text() == "x = 1\ny = 20\nz = 3\n"


def test_apply_creates_new_file_and_appends_when_context_missing(tmp_path):
    (tmp_path / "b.py").write_text("keep\n")
    diff = (
        "diff --git a/new.py b/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+one\n+two\n"
        "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -1,2 +1,2 @@\n nothere\n-gone\n+added\n"
    )
    ctr.apply_diff(tmp_path, diff)
    assert (tmp_path / "new.py").read_text() == "one\ntwo\n"
    assert (tmp_path / "b.py").read_text() == "keep\nadded\n"


def test_every_sample_becomes_a_branch_that_differs_from_main(tmp_path):
    samples = load_samples(ROOT / "samples" / "prs.json")
    prs = ctr.build_local_repo(tmp_path, samples)
    assert len(prs) == len(samples)
    for p in prs:
        out = subprocess.run(["git", "diff", "--stat", f"main...{p['branch']}"], cwd=tmp_path,
                             capture_output=True, text=True).stdout
        assert out.strip(), p["branch"]
    good = subprocess.run(["git", "show", "pr-good-fix:tinydate/parser.py"], cwd=tmp_path,
                          capture_output=True, text=True).stdout
    assert "raise ValueError" in good


def test_live_mode_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_WRITE_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["create_test_repo.py"])
    with pytest.raises(SystemExit) as e:
        ctr.main()
    assert "GITHUB_WRITE_TOKEN" in str(e.value)
