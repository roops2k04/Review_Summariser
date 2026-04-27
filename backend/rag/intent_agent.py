import re


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def detect_intent(question: str) -> dict:
    """Very simple rule-based intent agent for analysis routing.

    Returns a lightweight plan used by the backend:
      - intent: label for observability
      - mode: pros_only | cons_only | both
      - top_k: retrieval depth hint
      - confidence: 0.0 to 1.0
    """
    q = _normalize(question)
    if not q:
        return {
            "intent": "general_analysis",
            "mode": "both",
            "top_k": 30,
            "confidence": 0.65,
        }

    pros_terms = ["pro", "pros", "advantage", "advantages", "positive", "positives", "good points"]
    cons_terms = ["con", "cons", "disadvantage", "disadvantages", "negative", "negatives", "drawback", "drawbacks", "issues", "problems"]
    price_terms = ["price", "pricing", "cost", "expensive", "cheap", "value"]
    service_terms = ["service", "staff", "wait", "delay", "behavior", "attitude"]
    food_terms = ["food", "taste", "quality", "fresh", "menu", "portion"]

    asks_pros = any(t in q for t in pros_terms)
    asks_cons = any(t in q for t in cons_terms)

    intent = "general_analysis"
    mode = "both"
    top_k = 30
    confidence = 0.72

    if asks_cons and not asks_pros:
        intent = "cons_analysis"
        mode = "cons_only"
        top_k = 26
        confidence = 0.92
    elif asks_pros and not asks_cons:
        intent = "pros_analysis"
        mode = "pros_only"
        top_k = 26
        confidence = 0.92
    elif asks_pros and asks_cons:
        intent = "pros_cons_analysis"
        mode = "both"
        top_k = 32
        confidence = 0.95

    if any(t in q for t in price_terms):
        intent = "price_focus"
        top_k = max(top_k, 36)
        confidence = max(confidence, 0.82)
    elif any(t in q for t in service_terms):
        intent = "service_focus"
        top_k = max(top_k, 34)
        confidence = max(confidence, 0.82)
    elif any(t in q for t in food_terms):
        intent = "food_focus"
        top_k = max(top_k, 34)
        confidence = max(confidence, 0.80)

    return {
        "intent": intent,
        "mode": mode,
        "top_k": top_k,
        "confidence": round(confidence, 2),
    }
