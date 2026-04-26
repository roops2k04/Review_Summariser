from services.places import search_places, get_reviews

# change query as you like
query = "Taj Hotel in Mumbai"

# Step 1: search places
places = search_places(query)

print("\n=== PLACES FOUND ===")
for p in places:
    print(f"{p['name']} (Rating: {p['rating']})")

# Step 2: fetch reviews
print("\n=== REVIEWS FROM GOOGLE API ===")

for place in places:
    print(f"\n📍 {place['name']}")
    print("-" * 50)

    reviews = get_reviews(place["place_id"])

    if not reviews:
        print("No reviews found.")
        continue

    for i, r in enumerate(reviews, 1):
        print(f"{i}. {r}\n")