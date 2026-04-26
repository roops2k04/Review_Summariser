import chromadb

# In-memory ChromaDB client (singleton)
_client = chromadb.Client()
COLLECTION_NAME = "reviews_collection"


def get_collection(reset: bool = True):
    """Return (and optionally reset) the ChromaDB collection."""
    if reset:
        try:
            _client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def store_chunks(chunks: list[str], embeddings: list[list[float]]) -> None:
    """Store text chunks with their embeddings in ChromaDB."""
    if not chunks:
        return
    collection = get_collection(reset=True)
    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[str(i) for i in range(len(chunks))],
    )


def query_chunks(query_embedding: list[float], top_k: int = 20) -> list[str]:
    """Retrieve top-K most relevant chunks from ChromaDB."""
    try:
        collection = get_collection(reset=False)
    except Exception:
        return []
    count = collection.count()
    if count == 0:
        return []
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
    )
    return results["documents"][0] if results["documents"] else []
