from rag.embedder import embed_texts, embed_query
from rag.vectorstore import store_chunks, query_chunks


def index_and_retrieve(chunks: list[str], question: str, top_k: int = 20) -> list[str]:
    """
    Full RAG pipeline:
      1. Embed all chunks
      2. Store in ChromaDB
      3. Embed the query
      4. Retrieve top-K relevant chunks
    Returns the retrieved chunk strings.
    """
    if not chunks:
        return []

    # Step 1 & 2: embed + store
    embeddings = embed_texts(chunks)
    store_chunks(chunks, embeddings)

    # Step 3 & 4: embed query + retrieve
    q_embedding = embed_query(question)
    return query_chunks(q_embedding, top_k=top_k)
