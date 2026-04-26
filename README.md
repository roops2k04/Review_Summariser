# ReviewLens v2 — Local Business Review Analyzer

RAG-powered AI that finds multiple outlets, shows review counts, and delivers exactly 5 Pros + 5 Cons.

## Architecture

```
review-analyzer-v2/
├── backend/
│   ├── app.py                  ← FastAPI (2 endpoints: /api/search + /api/analyze)
│   ├── requirements.txt
│   ├── .env                    ← Your API keys (copy from .env.example)
│   └── rag/
│       ├── scraper.py          ← Serper API: search_places() + fetch_reviews_for_place()
│       ├── processor.py        ← clean + chunk + deduplicate reviews
│       ├── embedder.py         ← SentenceTransformer embeddings (separate file)
│       ├── vectorstore.py      ← ChromaDB store + query (separate file)
│       ├── retriever.py        ← Orchestrates embed→store→retrieve (separate file)
│       └── llm.py              ← Grok/Groq: generates strict 5 pros + 5 cons JSON
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

## Two-Step Flow

1. **Search** → returns all outlets in the city with name, address, review count  
2. **Select outlet** → fetches 100+ reviews, RAG pipeline, returns 5 Pros + 5 Cons

## Setup

```bash
cd backend
cp ../.env.example .env
# Edit .env and add your keys

pip install -r requirements.txt
python app.py
```

Open http://localhost:8000

## API Keys

| Variable | Source |
|---|---|
| SERPER_API_KEY | https://serper.dev |
| XAI_API_KEY | https://console.x.ai (Grok) OR https://console.groq.com (free, key starts with gsk_) |

## Endpoints

### POST /api/search
```json
{ "query": "Pizza Hut", "location": "Hyderabad" }
```
Returns list of outlets with review counts.

### POST /api/analyze
```json
{ "cid": "...", "name": "...", "address": "...", "snippet": "...", "question": "..." }
```
Returns 5 pros, 5 cons, summary, source excerpts, stats.
