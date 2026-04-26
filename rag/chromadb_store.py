from functools import lru_cache
from pathlib import Path

from .embedding import embed_query, embed_texts


@lru_cache(maxsize=1)
def get_client():
    import chromadb

    db_path = Path(__file__).resolve().parents[1] / ".chroma_db"
    return chromadb.PersistentClient(path=str(db_path))

@lru_cache(maxsize=1)
def get_collection():
    client = get_client()
    return client.get_or_create_collection(name="reviews")

def store_chunks(place, chunks):
    if not chunks:
        return

    collection = get_collection()
    embeddings = embed_texts(chunks)

    collection.upsert(
        documents=chunks,
        embeddings=embeddings,
        ids=[f"{place}_{index}" for index in range(len(chunks))],
        metadatas=[{"place": place}] * len(chunks),
    )


def retrieve_chunks(query, place, n_results=5):
    collection = get_collection()
    query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"place": place},
    )

    documents = results.get("documents", [])
    return documents[0] if documents else []