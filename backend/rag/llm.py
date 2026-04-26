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
3. If the reviews contain fewer than 5 clear pros or cons, fill remaining slots with "Not enough data in reviews"
4. You MUST always return all 5 pros and all 5 cons — never fewer
5. Return ONLY a raw JSON object — no markdown, no explanation, no extra text

REQUIRED FORMAT (raw JSON only):
{
  "pros": ["specific pro 1", "specific pro 2", "specific pro 3", "specific pro 4", "specific pro 5"],
  "cons": ["specific con 1", "specific con 2", "specific con 3", "specific con 4", "specific con 5"],
  "summary": "2-3 sentence factual summary based strictly on the reviews"
}

REVIEW EXCERPTS TO ANALYZE:
"""


def generate_pros_cons(chunks: list[str], question: str) -> dict:
    client, model = _get_client()

    # Use all chunks for maximum context — join with separator
    context = "\n---\n".join(chunks)
    print(f"[llm] sending {len(chunks)} chunks ({len(context)} chars) to LLM")

    user_msg = (
        f"Analyze all the review excerpts provided and extract exactly 5 pros and 5 cons.\n"
        f"User's specific question: {question}\n"
        f"Remember: return raw JSON only, always include all 5 pros and 5 cons."
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

            # Pad to exactly 5 if LLM returned fewer
            while len(pros) < 5:
                pros.append("Not enough data in reviews")
            while len(cons) < 5:
                cons.append("Not enough data in reviews")

            return {
                "pros":    pros[:5],
                "cons":    cons[:5],
                "summary": result.get("summary", ""),
            }

        except Exception as e:
            print(f"[llm] attempt {attempt+1} error: {e}")
            if attempt == 1:
                # Both attempts failed — return structured error
                return {
                    "pros":    ["LLM API error — check XAI_API_KEY"] + ["Not available"] * 4,
                    "cons":    [str(e)[:80]] + ["Not available"] * 4,
                    "summary": f"Could not generate AI analysis. Error: {e}",
                }
