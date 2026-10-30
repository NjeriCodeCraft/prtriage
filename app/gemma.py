"""Calls Gemma 4 through the Gemini API and validates the JSON it returns."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from . import config
from .prompts import SYSTEM_PROMPT, VERDICTS


class GemmaError(Exception):
    """Raised when the model call fails or returns something unusable."""


@dataclass
class Judgement:
    verdict: str
    confidence: float
    reasons: list[str]
    concerns: list[str]
    injection_detected: bool
    suggested_reply: str


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_judgement(raw: str) -> Judgement:
    """Strip code fences, find the JSON object, validate its shape. Raises GemmaError on any problem."""
    if not raw or not raw.strip():
        raise GemmaError("Gemma returned an empty response.")
    text = _FENCE.sub("", raw.strip()).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise GemmaError("Gemma's response did not contain a JSON object.")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise GemmaError(f"Gemma's response was not valid JSON ({exc.msg}).") from exc
    if not isinstance(data, dict):
        raise GemmaError("Gemma's JSON was not an object.")

    verdict = data.get("verdict")
    if verdict not in VERDICTS:
        raise GemmaError(f"Gemma returned an unknown verdict: {verdict!r}.")
    reasons = data.get("reasons")
    if not isinstance(reasons, list) or not reasons or not all(isinstance(r, str) for r in reasons):
        raise GemmaError("Gemma's 'reasons' must be a non-empty list of strings.")
    concerns = data.get("concerns", [])
    if not isinstance(concerns, list) or not all(isinstance(c, str) for c in concerns):
        raise GemmaError("Gemma's 'concerns' must be a list of strings.")
    reply = data.get("suggested_reply", "")
    if not isinstance(reply, str):
        raise GemmaError("Gemma's 'suggested_reply' must be a string.")
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError) as exc:
        raise GemmaError("Gemma's 'confidence' must be a number.") from exc
    confidence = min(1.0, max(0.0, confidence))

    return Judgement(
        verdict=verdict,
        confidence=confidence,
        reasons=reasons[:5],
        concerns=concerns[:5],
        injection_detected=bool(data.get("injection_detected", False)),
        suggested_reply=reply.strip(),
    )


# A "model call" takes the user prompt and returns raw text. Tests swap this out.
ModelCall = Callable[[str], str]


def call_gemma(user_prompt: str) -> str:
    """Real call to the hosted Gemma 4 model. Returns raw text."""
    if not config.GEMINI_API_KEY:
        raise GemmaError("GEMINI_API_KEY is not set on the server.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise GemmaError("google-genai is not installed.") from exc

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    try:
        try:
            response = client.models.generate_content(
                model=config.MODEL_ID,
                contents=user_prompt,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.2),
            )
        except Exception as exc:  # some hosted models reject system_instruction
            if "instruction" not in str(exc).lower():
                raise
            response = client.models.generate_content(
                model=config.MODEL_ID,
                contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
                config=types.GenerateContentConfig(temperature=0.2),
            )
    except GemmaError:
        raise
    except Exception as exc:
        raise GemmaError(f"The Gemma call failed: {type(exc).__name__}: {exc}") from exc

    text = getattr(response, "text", None)
    if not text:
        raise GemmaError("Gemma returned no text.")
    return text


def judge(user_prompt: str, model_call: ModelCall | None = None, retries: int = 1) -> Judgement:
    """Call the model and validate. Retries once if the JSON is malformed. Raises GemmaError if it still fails."""
    call = model_call or call_gemma
    last_error: GemmaError | None = None
    for attempt in range(retries + 1):
        prompt = user_prompt if attempt == 0 else user_prompt + "\n\nYour previous reply was not valid JSON. Return ONLY the JSON object."
        raw = call(prompt)
        try:
            return parse_judgement(raw)
        except GemmaError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error
