import streamlit as st
import threading

from services.places import search_places, get_reviews
from rag.chunking import chunk_reviews
from rag.chromadb_store import store_chunks
from rag.retrieval import retrieve_relevant_chunks
from services.formatter import format_output
from services.llm import analyze_reviews, ask_llm
from services.parser import parse_query
from rag.embedding import embed_query

st.title("💬 Review RAG Chatbot")


def _looks_like_place_search(user_text: str) -> bool:
    text = " ".join((user_text or "").strip().split()).lower()
    if not text:
        return False
    if "?" in text:
        return False

    # If the user is asking a specific question, don't force pros/cons.
    question_words = {
        "what",
        "why",
        "how",
        "where",
        "when",
        "does",
        "do",
        "is",
        "are",
        "can",
        "should",
        "price",
        "cost",
        "rate",
        "rating",
    }
    tokens = set(text.replace(",", " ").replace(".", " ").split())
    if tokens & question_words:
        return False

    # Heuristic: short, descriptive text is likely a place search.
    return len(text.split()) <= 10


@st.cache_resource
def _warm_embedding_model():
    # Warm up in the background so first page load doesn't block.
    def _run():
        try:
            embed_query("warmup")
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return True


_warm_embedding_model()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "indexed_places" not in st.session_state:
    st.session_state.indexed_places = set()

for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])

user_input = st.chat_input("Ask about any place...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.spinner("Fetching reviews and building answer..."):
        try:
            parsed = parse_query(user_input)

            # Step 1: Fetch place
            places = search_places(parsed["query"])

            if not places:
                message = "No place found"
                st.session_state.messages.append({"role": "assistant", "content": message})
                st.chat_message("assistant").write(message)
            else:
                place = places[0]
                place_name = place["name"]
                place_id = place["place_id"]

                # Step 2: Fetch reviews
                reviews = get_reviews(place_id)

                if not reviews:
                    message = "No reviews found"
                    st.session_state.messages.append({"role": "assistant", "content": message})
                    st.chat_message("assistant").write(message)
                else:
                    # Step 3: Chunk
                    chunks = chunk_reviews(reviews)

                    # Step 4: Index once per place (avoids re-embedding on every chat message)
                    if place_id not in st.session_state.indexed_places:
                        store_chunks(place_id, chunks)
                        st.session_state.indexed_places.add(place_id)

                    rating = place.get("rating", "N/A")

                    # Step 5: Dense Vector Retrieval (Semantic Search)
                    retrieved = retrieve_relevant_chunks(user_input, place_id, n_results=12)

                    lower = user_input.lower()
                    wants_pros_cons = (("pros" in lower and "cons" in lower) or _looks_like_place_search(user_input))
                    if wants_pros_cons:
                        # For pros/cons, analyze across *all* reviews (not just retrieved),
                        # so negatives aren't missed.
                        analysis_chunks = chunks
                        result = analyze_reviews({place_name: analysis_chunks})
                        final = format_output(result, {place_name: rating})
                    else:
                        context = "\n".join(retrieved or [])
                        answer = ask_llm(user_input, context)
                        final = f"Place: {place_name} (Rating: {rating})\n\n{answer}"

                    st.session_state.messages.append({"role": "assistant", "content": final})
                    st.chat_message("assistant").write(final)
        except Exception as exc:
            message = f"Something went wrong while processing your request: {exc}"
            st.session_state.messages.append({"role": "assistant", "content": message})
            st.error(message)
