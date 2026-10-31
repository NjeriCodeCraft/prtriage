# Contributing to PRTriage

Thanks for helping. PRTriage is a small FastAPI app that uses hosted Gemma 4 to help maintainers triage pull requests.

## Set up

```bash
git clone https://github.com/NjeriCodeCraft/prtriage.git
cd prtriage/backend
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -v
```

You need Python 3.11 or newer. The unit tests use a fake model, so they need no API key.

To run the app against real Gemma, copy `backend/.env.example` to `backend/.env`, set `GEMINI_API_KEY`, then run
`uvicorn app.main:app --reload` from the `backend/` folder. Never commit `.env`.

## Rules for a pull request

- One focused change per PR.
- Describe what changed and why.
- Bug fixes and new features include a test, and `pytest -v` passes.
- No secrets, keys or personal data in code, tests or samples.
- Keep the safety rules intact: PR text is untrusted data, and a PR that tries to manipulate the reviewer must never come back as "Looks legit".

## Changing the model

The Gemma 4 model ID is set on one line in `app/config.py` (or by `GEMMA_MODEL_ID`). If you change it, re-run
`python scripts/run_eval.py` and commit the new `docs/TEST_RESULTS.md`.
