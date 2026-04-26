import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Backward-compatible LLM env vars (historically named GROK_*).
# Note: Groq API keys typically start with `gsk_`.
GROK_API_KEY = os.getenv("GROK_API_KEY") or os.getenv("GROQ_API_KEY")
GROK_MODEL = os.getenv("GROK_MODEL", "") or os.getenv("GROQ_MODEL", "")


def _infer_llm_provider(api_key: str | None) -> str:
	provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
	if provider in {"groq", "xai"}:
		return provider

	key = (api_key or "").strip()
	if key.startswith("gsk_"):
		return "groq"
	return "xai" if key else ""


LLM_PROVIDER = _infer_llm_provider(GROK_API_KEY)

if LLM_PROVIDER == "groq":
	LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
	_candidate_model = os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL") or GROK_MODEL
	if (_candidate_model or "").strip().lower().startswith("grok"):
		_candidate_model = ""
	LLM_MODEL = _candidate_model or "llama-3.1-8b-instant"
elif LLM_PROVIDER == "xai":
	LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.x.ai/v1")
	LLM_MODEL = os.getenv("LLM_MODEL") or GROK_MODEL or "grok-2-latest"
else:
	LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
	LLM_MODEL = os.getenv("LLM_MODEL") or GROK_MODEL or ""

LLM_API_KEY = GROK_API_KEY