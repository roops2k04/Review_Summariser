import os
import json
import re
from openai import OpenAI


def _get_client():
    key = os.getenv("XAI_API_KEY", "")
    if not key:
        raise ValueError("XAI_API_KEY is not set in backend/.env")
    if key.startswith("gsk_"):
        client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        model  = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    else:
        client = OpenAI(api_key=key, base_url="https://api.x.ai/v1")
        model  = os.getenv("XAI_MODEL", "grok-beta")
    print(f"[llm] using model={model}")
    return client, model


SYSTEM_PROMPT = """You are a strict review analyst extracting insights from customer reviews.

YOUR TASK: Extract exactly 5 PROS and 5 CONS from the review excerpts provided.

STRICT RULES:
1. Use ONLY information from the review excerpts below — no outside knowledge
2. Each pro/con must be a specific, concrete point (not vague like "good food")
3. You MUST always return all 5 pros and all 5 cons — never fewer
4. Return ONLY a raw JSON object — no markdown, no explanation, no extra text

REQUIRED FORMAT (raw JSON only):
{
  "pros": ["specific pro 1", "specific pro 2", "specific pro 3", "specific pro 4", "specific pro 5"],
  "cons": ["specific con 1", "specific con 2", "specific con 3", "specific con 4", "specific con 5"],
  "summary": "2-3 sentence factual summary based strictly on the reviews"
}

REVIEW EXCERPTS TO ANALYZE:
"""


def _detect_mode(question: str) -> str:
    q = (question or "").strip().lower()
    if not q:
        return "both"

    asks_pros = any(k in q for k in ["pro", "pros", "advantage", "advantages", "good", "positives"])
    asks_cons = any(k in q for k in ["con", "cons", "disadvantage", "disadvantages", "bad", "negatives", "drawbacks"])

    if asks_cons and not asks_pros:
        return "cons_only"
    if asks_pros and not asks_cons:
        return "pros_only"
    return "both"


def generate_pros_cons(chunks: list[str], question: str, forced_mode: str | None = None) -> dict:
    client, model = _get_client()
    mode = forced_mode or _detect_mode(question)

    # Use all chunks for maximum context — join with separator
    context = "\n---\n".join(chunks)
    print(f"[llm] sending {len(chunks)} chunks ({len(context)} chars) to LLM")

    if mode == "cons_only":
        task_instruction = (
            "Analyze all the review excerpts and return ONLY 5 cons. "
            "Set pros to an empty array []."
        )
    elif mode == "pros_only":
        task_instruction = (
            "Analyze all the review excerpts and return ONLY 5 pros. "
            "Set cons to an empty array []."
        )
    else:
        task_instruction = "Analyze all the review excerpts and return 5 pros and 5 cons."

    user_msg = (
        f"{task_instruction}\n"
        f"User's specific question: {question}\n"
        "Return raw JSON only with keys: pros, cons, summary."
    )

    # Try with json_object response format first
    for attempt in range(2):
        try:
            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + context},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=1000,
            )
            if attempt == 0:
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)
            raw  = resp.choices[0].message.content.strip()
            print(f"[llm] raw response (attempt {attempt+1}): {raw[:200]}")

            # Strip markdown fences if present
            raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
            result = json.loads(raw)

            # Validate shape
            pros = result.get("pros", [])
            cons = result.get("cons", [])

            # Enforce question intent strictly, even if model returns extra fields.
            if mode == "cons_only":
                pros = []
                while len(cons) < 5:
                    cons.append("Not enough data in reviews")
            elif mode == "pros_only":
                cons = []
                while len(pros) < 5:
                    pros.append("Not enough data in reviews")
            else:
                while len(pros) < 5:
                    pros.append("Not enough data in reviews")
                while len(cons) < 5:
                    cons.append("Not enough data in reviews")

            return {
                "pros":    pros[:5],
                "cons":    cons[:5],
                "summary": result.get("summary", ""),
                "mode":    mode,
            }

        except Exception as e:
            print(f"[llm] attempt {attempt+1} error: {e}")
            if attempt == 1:
                # Both attempts failed — return structured error
                return {
                    "pros":    ["LLM API error — check XAI_API_KEY"] + ["Not available"] * 4,
                    "cons":    [str(e)[:80]] + ["Not available"] * 4,
                    "summary": f"Could not generate AI analysis. Error: {e}",
                    "mode":    mode,
                }
