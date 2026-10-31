"""Central configuration. The Gemma 4 model ID lives on ONE line below."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- The one place the model ID is set. Shown in the UI footer and /api/config. ---
MODEL_ID = os.getenv("GEMMA_MODEL_ID", "gemma-4-26b-a4b-it")
# Other model listed in the Starter Kit: gemma-4-31b-it

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # optional, raises GitHub rate limit

MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "12000"))
MAX_BODY_CHARS = int(os.getenv("MAX_BODY_CHARS", "4000"))
MAX_CONTRIBUTING_CHARS = int(os.getenv("MAX_CONTRIBUTING_CHARS", "4000"))
GEMMA_TIMEOUT_SECONDS = int(os.getenv("GEMMA_TIMEOUT_SECONDS", "60"))
# Max triage requests per client per minute (each one costs a Gemma call). 0 turns the limit off.
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

MODEL_LICENSE_URL = "https://www.apache.org/licenses/LICENSE-2.0"
GEMINI_API_TERMS_URL = "https://ai.google.dev/gemini-api/terms"
