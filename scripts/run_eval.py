"""Runs every synthetic sample PR through the REAL Gemma model and writes docs/TEST_RESULTS.md.

Usage:  GEMINI_API_KEY=... python scripts/run_eval.py

Results are whatever the model actually returned. Nothing is hard-coded as passed.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402
from app.samples import load_samples  # noqa: E402
from app.triage import triage  # noqa: E402


def main() -> int:
    if not config.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set. Nothing was run.")
        return 1

    rows, details = [], []
    for s in load_samples(ROOT / "samples" / "prs.json"):
        r = triage(s["title"], s["body"], s["diff"], s["contributing"])
        if r.error:
            outcome = "ERROR (model call failed or returned unusable output)"
        elif r.verdict in s["expected"]:
            outcome = "as expected"
        else:
            outcome = f"DIFFERENT from expected {s['expected']}"
        rows.append(f"| {s['id']} | {s['category']} | {', '.join(s['expected'])} | {r.verdict_label} | "
                    f"{'yes' if r.injection_detected else 'no'} | {'yes' if r.diff_truncated else 'no'} | {outcome} |")
        details.append(f"### {s['id']}\n- Verdict: **{r.verdict_label}** (confidence {r.confidence:.2f})\n"
                       f"- Error: {r.error or 'none'}\n- Reasons: " + "; ".join(r.reasons) +
                       "\n- Concerns: " + ("; ".join(r.concerns) or "none") + "\n")

    out = ROOT / "docs" / "TEST_RESULTS.md"
    out.write_text(
        f"# Test results (live Gemma run)\n\nModel: `{config.MODEL_ID}`  \nRun at: {datetime.now(timezone.utc).isoformat()}\n\n"
        "These are the real outputs from the hosted model on the synthetic sample PRs in `samples/prs.json`.\n"
        "Rows marked DIFFERENT or ERROR are reported as they happened, not hidden.\n\n"
        "| Sample | Category | Accepted verdicts | Gemma verdict | Injection flagged | Diff truncated | Outcome |\n"
        "|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Details\n\n" + "\n".join(details),
        encoding="utf-8",
    )
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
