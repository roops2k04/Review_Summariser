import re


def parse_query(user_input):
    text = " ".join(user_input.strip().split())
    if not text:
        return {"location": "chennai", "type": "cafe", "query": "cafe in chennai"}

    lower = text.lower()
    location = "chennai"
    subject = text

    if " in " in lower:
        idx = lower.rfind(" in ")
        subject = text[:idx].strip(" ?.,")
        location = text[idx + 4 :].strip(" ?.,") or "chennai"

    subject = re.sub(r"^(ask|please)\s+", "", subject, flags=re.IGNORECASE)

    subject = re.sub(
        r"^(reviews?\s+(for|about)|review\s+of|about|show\s+me|find|tell\s+me\s+about)\s+",
        "",
        subject,
        flags=re.IGNORECASE,
    ).strip(" ?.,")

    if not subject:
        subject = "cafe"

    return {
        "location": location,
        "type": subject,
        "query": f"{subject} in {location}",
    }