# Deploying to PrimeCloud

**Status: NOT DEPLOYED YET.** Fill in the blanks below as you go, with what you actually did. Judges want a working
public URL, not a dashboard screenshot.

## What the app needs from any host
- Python 3.11+ (or use the included `Dockerfile`, or the `Procfile`).
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables (set in the host's secrets / env settings, never in git):
  - `GEMINI_API_KEY` (required)
  - `GEMMA_MODEL_ID` (optional, defaults to `gemma-4-26b-a4b-it`)
  - `GITHUB_TOKEN` (optional)
- Health check path: `/healthz`
- Port: the app reads `$PORT` in the Docker/Procfile start command.

## Questions to ask PrimeCloud staff at the venue (answers go below)
1. Which deploy route works for a Python app: container image, or Git repo? ______
2. Exact commands / buttons to deploy it? ______
3. How are secrets / environment variables set? ______
4. Which port should the app listen on, and is `$PORT` provided? ______
5. Their submission cutoff, if it differs from the main event? ______

## Steps I actually followed
1. ______
2. ______

## Result
- Live URL: ______
- Checked from a private/incognito window on: ______ (date/time)
- Hello-world deployed first on: ______


## Update: repo is split into backend/ and frontend/

In PrimeCloud set **Root directory = `backend`**. The Dockerfile is `backend/Dockerfile`. The page is hosted on Vercel (Root Directory = `frontend`), see README.
