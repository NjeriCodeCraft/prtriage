"""Loads the synthetic test PRs. Entries can ask for a generated huge diff."""
from __future__ import annotations

import json
from pathlib import Path


def _huge_diff(lines: int) -> str:
    header = "diff --git a/data/table.py b/data/table.py\n--- a/data/table.py\n+++ b/data/table.py\n@@ -0,0 +1,%d @@\n" % lines
    return header + "\n".join(f"+ROW_{i} = {i * 7}" for i in range(lines))


def load_samples(path: Path) -> list[dict]:
    samples = json.loads(Path(path).read_text(encoding="utf-8"))
    for s in samples:
        if "generate_huge_diff_lines" in s:
            s["diff"] = _huge_diff(int(s["generate_huge_diff_lines"]))
    return samples
