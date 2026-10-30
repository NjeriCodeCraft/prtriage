"""Triage pipeline: truncate -> build prompt -> Gemma -> validate -> safety checks -> result."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from . import config
from .gemma import GemmaError, ModelCall, judge
from .prompts import VERDICT_LABELS, build_user_prompt

# Cheap code-side tripwire. Gemma is the judge; this only catches obvious manipulation attempts
# so a successful injection can never silently produce "Looks legit".
INJECTION_PATTERNS = [
    r"ignore (all |any |your |the )?(previous |prior |above )?(instructions|rules|prompt)",
    r"disregard (all |any |your |the )?(previous |prior |above )?(instructions|rules|prompt)",
    r"mark (this|it) as (legit|legitimate|approved|good)",
    r"(you are|you're) now\b",
    r"system prompt",
    r"as an ai (language )?model",
    r"output (only )?(the following|this) json",
    r"\"verdict\"\s*:\s*\"looks_legit\"",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def detect_injection(*texts: str) -> bool:
    return any(_INJECTION_RE.search(t or "") for t in texts)


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n... [truncated]", True


@dataclass
class TriageResult:
    verdict: str
    verdict_label: str
    confidence: float
    reasons: list[str]
    concerns: list[str]
    injection_detected: bool
    suggested_reply: str
    diff_truncated: bool
    model: str = config.MODEL_ID
    error: str | None = None
    signals: dict = field(default_factory=dict)  # displayed only, never used for the verdict

    def to_dict(self) -> dict:
        return asdict(self)


def _unsure(error: str, diff_truncated: bool, signals: dict | None = None) -> TriageResult:
    return TriageResult(
        verdict="unsure",
        verdict_label=VERDICT_LABELS["unsure"],
        confidence=0.0,
        reasons=["The model could not produce a reliable judgement, so no recommendation is made."],
        concerns=[],
        injection_detected=False,
        suggested_reply="",
        diff_truncated=diff_truncated,
        error=error,
        signals=signals or {},
    )


def triage(title: str, body: str, diff: str, contributing: str | None,
           signals: dict | None = None, model_call: ModelCall | None = None) -> TriageResult:
    title = (title or "").strip()[:300]
    body, _ = truncate(body or "", config.MAX_BODY_CHARS)
    diff, diff_truncated = truncate(diff or "", config.MAX_DIFF_CHARS)
    if contributing:
        contributing, _ = truncate(contributing, config.MAX_CONTRIBUTING_CHARS)

    if not (title or body.strip() or diff.strip()):
        return _unsure("Nothing to triage: title, description and diff are all empty.", False, signals)

    prompt = build_user_prompt(title, body, diff, contributing, diff_truncated)
    try:
        j = judge(prompt, model_call=model_call)
    except GemmaError as exc:
        return _unsure(str(exc), diff_truncated, signals)

    tripwire = detect_injection(title, body, diff, contributing or "")
    verdict = j.verdict
    concerns = list(j.concerns)
    injection = j.injection_detected or tripwire
    if injection and not j.injection_detected:
        concerns.append("Safety check: the PR text contains wording that tries to instruct the reviewer or the AI.")
    confidence = j.confidence
    reply = j.suggested_reply
    if injection and verdict == "looks_legit":
        verdict = "unsure"
        confidence = min(confidence, 0.5)
        concerns.append("Downgraded from 'Looks legit' because the PR attempted prompt injection. A human must review it.")
    if injection:
        # Model text written while reading attacker-controlled input is not offered to the maintainer.
        reply = ""
        concerns.append("No reply is suggested because the PR text tried to steer the AI. Write your own.")

    return TriageResult(
        verdict=verdict,
        verdict_label=VERDICT_LABELS[verdict],
        confidence=confidence,
        reasons=j.reasons,
        concerns=concerns,
        injection_detected=injection,
        suggested_reply=reply,
        diff_truncated=diff_truncated,
        signals=signals or {},
    )
