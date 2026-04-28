
import os
import re
import requests


def _extract_review_count(p: dict) -> int:
    """Try every field name/shape Serper might use for review count."""

    def _to_int(val) -> int:
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val)
        nums = re.findall(r"\d[\d,]*", s)
        if not nums:
            return 0
        try:
            return int(nums[0].replace(",", ""))
        except Exception:
            return 0

    # Debug: print keys so we can inspect live payload shape.
    print(f"  [DEBUG] place keys: { {k: v for k, v in p.items() if k not in ['photos']} }")

    for field in [
        "reviewsCount",      # most common in Serper Places API
        "ratingCount",
        "reviewCount",
        "reviews",
        "userRatingsTotal",
        "totalScore",
        "numReviews",
        "ratingsTotal",
    ]:
        val = p.get(field)
        if val is not None and val != "":
            count = _to_int(val)
            if count > 0:
                print(f"  [DEBUG] review count found in field '{field}': {count}")
                return count

    # Some payloads nest the count under rating/reviews objects.
    for field in ["rating", "reviews", "about", "attributes"]:
        obj = p.get(field)
        if isinstance(obj, dict):
            for nested_key in ["count", "total", "reviewsCount", "ratingCount", "userRatingsTotal"]:
                count = _to_int(obj.get(nested_key))
                if count > 0:
                    print(f"  [DEBUG] review count found in nested '{field}.{nested_key}': {count}")
                    return count

    # Last-resort parse from free text fields.
    for field in ["snippet", "description", "address", "title"]:
        val = p.get(field)
        if not val:
            continue
        count = _to_int(val)
        if count > 50:  # Avoid accidental extraction from house numbers etc.
            print(f"  [DEBUG] review count inferred from text field '{field}': {count}")
            return count

    return 0


def _extract_count_from_reviews_payload(payload: dict) -> int:
    """Scan /reviews response for a total-count signal."""

    def _to_int(val) -> int:
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val)
        nums = re.findall(r"\d[\d,]*", s)
        if not nums:
            return 0
        try:
            return int(nums[0].replace(",", ""))
        except Exception:
            return 0

    candidates = []

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                lk = str(k).lower()
                if any(token in lk for token in ["review", "rating", "count", "total"]):
                    n = _to_int(v)
                    if n > 0:
                        candidates.append(n)
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(payload)
    return max(candidates) if candidates else 0


def _fetch_review_count_by_cid(cid: str, headers: dict) -> int:
    """Fallback lookup: query /reviews page 1 and infer the place's total review count."""
    if not cid:
        return 0
    try:
        resp = requests.post(
            "https://google.serper.dev/reviews",
            headers=headers,
            json={"cid": cid, "page": 1},
            timeout=15,
        )
        if resp.status_code != 200:
            return 0
        data = resp.json()
        total = _extract_count_from_reviews_payload(data)
        if total > 0:
            print(f"  [DEBUG] review count from /reviews payload: {total}")
            return total
        return len(data.get("reviews", []))
    except Exception as e:
        print(f"  [DEBUG] /reviews count fallback error for cid={cid}: {e}")
        return 0


def search_places(search_term: str) -> list[dict]:
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("SERPER_API_KEY is not set in backend/.env")

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    resp = requests.post(
        "https://google.serper.dev/places",
        headers=headers,
        json={"q": search_term},
        timeout=15,
    )
    if resp.status_code != 200:
        raise Exception(f"Serper Places API Error: {resp.status_code} - {resp.text}")

    raw = resp.json().get("places", [])
    print(f"[scraper] search_places: found {len(raw)} raw places for '{search_term}'")

    results = []
    for p in raw[:10]:
        rc = _extract_review_count(p)
        if rc <= 0:
            rc = _fetch_review_count_by_cid(p.get("cid", ""), headers)
        entry = {
            "name":         p.get("title", "Unknown"),
            "address":      p.get("address", "Address not available"),
            "cid":          p.get("cid", ""),
            "rating":       p.get("rating", ""),
            "review_count": rc,
            "snippet":      p.get("snippet", ""),
            "phone":        p.get("phoneNumber", ""),
            "website":      p.get("website", ""),
        }
        print(f"  → {entry['name']} | cid={entry['cid']} | rating={entry['rating']} | reviews={entry['review_count']}")
        results.append(entry)
    return results


def fetch_reviews_for_place(
    cid: str,
    place_name: str = "",
    location: str = "",
    fallback_snippet: str = "",
) -> list[str]:
    """
    Multi-strategy review fetcher targeting 100+ reviews:
    Strategy 1: Serper /reviews API with pagination (main source)
    Strategy 2: Serper /search for review-rich pages about the business
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("SERPER_API_KEY is not set in backend/.env")

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    all_reviews = []

    # ── Strategy 1: Paginated /reviews API ──────────────────────────────
    if cid:
        print(f"[scraper] Fetching reviews via /reviews API for cid={cid}")
        for page in range(1, 16):   # up to 15 pages → ~150 reviews
            try:
                resp = requests.post(
                    "https://google.serper.dev/reviews",
                    headers=headers,
                    json={"cid": cid, "page": page},
                    timeout=15,
                )
                if resp.status_code != 200:
                    print(f"  [scraper] /reviews page {page} returned {resp.status_code}, stopping")
                    break
                data    = resp.json()
                fetched = data.get("reviews", [])
                print(f"  [scraper] page {page}: got {len(fetched)} reviews")
                if not fetched:
                    break
                for r in fetched:
                    snippet = (r.get("snippet") or r.get("text") or r.get("body") or "").strip()
                    if snippet and len(snippet) > 20:
                        all_reviews.append(snippet)
                if len(fetched) < 5:
                    break   # last page
            except Exception as e:
                print(f"  [scraper] /reviews page {page} error: {e}")
                break
        print(f"[scraper] Strategy 1 collected {len(all_reviews)} reviews")
    else:
        print("[scraper] No CID available, skipping /reviews API")

    # ── Strategy 2: Web search for more reviews if < 60 ────────────────
    if len(all_reviews) < 60 and (place_name or location):
        print(f"[scraper] Only {len(all_reviews)} so far — trying web search strategy")
        queries = []
        if place_name and location:
            queries = [
                f"{place_name} {location} reviews",
                f"{place_name} {location} customer reviews food quality",
            ]
        elif place_name:
            queries = [f"{place_name} reviews"]

        for q in queries:
            try:
                resp = requests.post(
                    "https://google.serper.dev/search",
                    headers=headers,
                    json={"q": q, "num": 10},
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for item in data.get("organic", []):
                    snippet = item.get("snippet", "").strip()
                    if snippet and len(snippet) > 30:
                        all_reviews.append(snippet)
                for key in ["answerBox", "knowledgeGraph"]:
                    obj = data.get(key, {})
                    if isinstance(obj, dict):
                        for k in ["snippet", "description", "answer"]:
                            val = obj.get(k, "").strip()
                            if val and len(val) > 30:
                                all_reviews.append(val)
                print(f"  [scraper] web search '{q}': now have {len(all_reviews)} total")
            except Exception as e:
                print(f"  [scraper] web search error: {e}")

    # ── Fallback ────────────────────────────────────────────────────────
    if not all_reviews and fallback_snippet:
        print("[scraper] Using fallback snippet only")
        all_reviews.append(fallback_snippet)

    # Deduplicate preserving order
    seen, deduped = set(), []
    for r in all_reviews:
        if r not in seen:
            seen.add(r)
            deduped.append(r)

    print(f"[scraper] Final: {len(deduped)} unique reviews collected")
    return deduped