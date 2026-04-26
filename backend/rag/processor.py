import re


def clean_text(text: str) -> str:
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 2) -> list[str]:
    """Split into sentences, group chunk_size sentences per chunk."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    chunks = []
    for i in range(0, len(sentences), chunk_size):
        chunk = " ".join(sentences[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


def process_reviews(reviews: list[str]) -> list[str]:
    """Clean, chunk, and deduplicate all reviews."""
    seen = set()
    all_chunks = []
    for review in reviews:
        cleaned = clean_text(review)
        if not cleaned or len(cleaned) < 20:
            continue
        for chunk in chunk_text(cleaned):
            if chunk not in seen:
                seen.add(chunk)
                all_chunks.append(chunk)
    return all_chunks
