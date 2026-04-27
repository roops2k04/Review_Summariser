import os
import re
import threading
import webbrowser
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from rag.scraper import search_places, fetch_reviews_for_place
from rag.processor import process_reviews
from rag.retriever import index_and_retrieve
from rag.llm import generate_pros_cons
from rag.intent_agent import detect_intent
# REPLACE this:
load_dotenv()

# WITH this:
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="ReviewLens ")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    location: str


class AnalyzeRequest(BaseModel):
    cid: str
    name: str
    address: str
    location: str = ""
    snippet: str  = ""
    question: str


def _normalize_text(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _is_place_in_location(place: dict, location: str) -> bool:
    """Strict filter: every significant location token must appear in place metadata."""
    loc = _normalize_text(location)
    if not loc:
        return True

    tokens = [t for t in loc.split(" ") if len(t) >= 3]
    if not tokens:
        tokens = loc.split(" ")

    searchable = _normalize_text(
        " ".join(
            [
                str(place.get("name", "")),
                str(place.get("address", "")),
                str(place.get("snippet", "")),
            ]
        )
    )

    return all(token in searchable for token in tokens)


# ── ENDPOINT 1: Search outlets ──────────────────────────────────────────
@app.post("/api/search")
async def search_endpoint(req: SearchRequest):
    try:
        term   = f"{req.query} in {req.location}"
        places = search_places(term)
        places = [p for p in places if _is_place_in_location(p, req.location)]
        if not places:
            raise HTTPException(404, f"No outlets found in {req.location}.")
        return {"places": places, "search_term": term}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Search failed: {e}")


# ── ENDPOINT 2: Analyze selected outlet ─────────────────────────────────
@app.post("/api/analyze")
async def analyze_endpoint(req: AnalyzeRequest):
    try:
        print(f"\n{'='*60}")
        print(f"[app] Analyzing: {req.name} | cid={req.cid}")

        # STEP 1: Fetch reviews (multi-strategy, targets 100+)
        raw_reviews = fetch_reviews_for_place(
            cid=req.cid,
            place_name=req.name,
            location=req.location,
            fallback_snippet=req.snippet,
        )
        print(f"[app] raw_reviews fetched: {len(raw_reviews)}")

        if not raw_reviews:
            raise HTTPException(404, "No reviews found for this outlet.")

        # STEP 2: Clean + chunk
        chunks = process_reviews(raw_reviews)
        print(f"[app] chunks after processing: {len(chunks)}")

        if not chunks:
            raise HTTPException(404, "Could not extract meaningful content from reviews.")

        # STEP 3: Intent agent decides mode + retrieval depth
        question = req.question or f"What are the pros and cons of {req.name}?"
        intent = detect_intent(question)
        top_k = int(intent.get("top_k", 30))
        relevant = index_and_retrieve(chunks, question, top_k=top_k)
        print(f"[app] relevant chunks retrieved: {len(relevant)}")

        # Use all relevant chunks; fall back to first 30 raw chunks
        llm_input = relevant if relevant else chunks[:30]

        # STEP 4: Generate 5 pros + 5 cons
        result = generate_pros_cons(llm_input, question, forced_mode=intent.get("mode"))

        return {
            "name":             req.name,
            "address":          req.address,
            "total_reviews":    len(raw_reviews),
            "total_chunks":     len(chunks),
            "chunks_retrieved": len(relevant),
            "question_used":    question,
            "analysis_mode":    result.get("mode", "both"),
            "intent":           intent,
            "pros":             result.get("pros", []),
            "cons":             result.get("cons", []),
            "summary":          result.get("summary", ""),
            "source_excerpts":  llm_input[:12],
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(502, f"Analysis failed: {e}")


# ── Mount frontend ───────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


# ── Run ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    def _open_browser():
        import time; time.sleep(1.8)
        webbrowser.open("http://localhost:8000")

    threading.Thread(target=_open_browser, daemon=True).start()
    print("\n ReviewLens starting → http://localhost:8000\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
