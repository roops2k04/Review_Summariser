from .chromadb_store import retrieve_chunks


def retrieve_relevant_chunks(query, place, n_results=8):
    return retrieve_chunks(query, place, n_results=n_results)
