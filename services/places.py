import requests
from config.settings import GOOGLE_API_KEY

def search_places(query):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    res = requests.get(url, params={
        "query": query,
        "key": GOOGLE_API_KEY
    }).json()

    return res.get("results", [])[:1]  # take best match


def get_reviews(place_id):
    """Fetch ALL available reviews for a place from Google API.
    
    Note: Google Places API returns multiple reviews per request (typically 5-30).
    To maximize reviews, we attempt multiple requests with the same place_id.
    """
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    
    all_reviews = []
    seen_reviews = set()
    
    # Make up to 3 requests to try to get more reviews
    for attempt in range(1):
        try:
            res = requests.get(url, params={
                "place_id": place_id,
                "fields": "reviews",
                "key": GOOGLE_API_KEY
            }).json()
            
            reviews = res.get("result", {}).get("reviews", [])
            for r in reviews:
                review_text = r.get("text", "").strip()
                if review_text and review_text not in seen_reviews:
                    all_reviews.append(review_text)
                    seen_reviews.add(review_text)
        except Exception as e:
            print(f"Error fetching reviews (attempt {attempt + 1}): {e}")
            continue
    
    return all_reviews