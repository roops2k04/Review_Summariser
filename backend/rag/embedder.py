from sentence_transformers import SentenceTransformer

_model = None


def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate normalized embeddings for a list of texts."""
    model = get_embedder()
    return model.encode(texts, normalize_embeddings=True).tolist()


def embed_query(query: str) -> list[float]:
    """Generate normalized embedding for a single query string."""
    model = get_embedder()
    return model.encode(query, normalize_embeddings=True).tolist()  # ← FIXED