"""FastAPI app: serves the UI and two triage endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import config
from .ratelimit import limit_triage
from .github_client import GitHubError, fetch_pr, list_open_prs
from .triage import triage

ROOT = Path(__file__).resolve().parent.parent
# The web page lives in ../frontend (hosted separately, e.g. Vercel). When that folder is next to this one
# (local development), the API also serves it at "/" so one command runs everything.
FRONTEND = ROOT.parent / "frontend"
SAMPLES = ROOT / "samples" / "prs.json"

app = FastAPI(title="PRTriage", description="AI-assisted pull request triage for open-source maintainers.")
# Open CORS (no cookies, no credentials) so a browser extension or another page can call the API.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


class UrlRequest(BaseModel):
    url: str = Field(..., max_length=300)


class TextRequest(BaseModel):
    title: str = Field("", max_length=300)
    body: str = Field("", max_length=20000)
    diff: str = Field("", max_length=200000)
    contributing: str | None = Field(None, max_length=20000)


@app.get("/")
def index():
    if (FRONTEND / "index.html").is_file():
        return FileResponse(FRONTEND / "index.html")
    return {"service": "PRTriage API", "docs": "/docs", "health": "/healthz"}


@app.get("/config.js")
def config_js():
    if (FRONTEND / "config.js").is_file():
        return FileResponse(FRONTEND / "config.js", media_type="application/javascript")
    raise HTTPException(status_code=404, detail="No frontend next to this API.")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    return {
        "model": config.MODEL_ID,
        "model_license_url": config.MODEL_LICENSE_URL,
        "gemini_api_terms_url": config.GEMINI_API_TERMS_URL,
        "api_key_configured": bool(config.GEMINI_API_KEY),
    }


@app.get("/api/samples")
def get_samples():
    from .samples import load_samples

    return [
        {k: v for k, v in s.items() if k in ("id", "label", "title", "body", "diff", "contributing")}
        for s in load_samples(SAMPLES)
    ]


@app.get("/api/repo-prs")
def repo_prs(url: str):
    try:
        return list_open_prs(url)
    except GitHubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/triage-url", dependencies=[Depends(limit_triage)])
def triage_url(req: UrlRequest):
    try:
        pr = fetch_pr(req.url)
    except GitHubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = triage(
        pr.title, pr.body, pr.diff, pr.contributing,
        signals={"author_account_age_days": pr.author_account_age_days,
                 "note": "Weak signal, shown for context only. It is not used for the verdict."},
    )
    return {"pr": {"owner": pr.owner, "repo": pr.repo, "number": pr.number, "title": pr.title},
            "diff_preview": pr.diff[:8000], **result.to_dict()}


@app.post("/api/triage-text", dependencies=[Depends(limit_triage)])
def triage_text(req: TextRequest):
    return triage(req.title, req.body, req.diff, req.contributing).to_dict()
