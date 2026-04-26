def chunk_reviews(reviews, chunk_size=200):
    # Keep each review intact to preserve full meaning and sentence boundaries.
    del chunk_size
    chunks = []
    seen = set()

    for review in reviews:
        text = " ".join((review or "").split()).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        chunks.append(text)

    return chunks
