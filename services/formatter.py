def format_output(result, ratings_map):
    output = ""

    for name, data in result.items():
        output += f"📍 {name}\n"
        output += f"⭐ Avg Rating: {ratings_map.get(name, 'N/A')}\n\n"

        output += "👍 Pros:\n"
        for p in data.get("pros", []):
            point = p.get("point", "")
            output += f"• {point}\n"

        output += "\n👎 Cons:\n"
        for c in data.get("cons", []):
            point = c.get("point", "")
            output += f"• {point}\n"

        output += "\n" + "─" * 50 + "\n\n"

    return output