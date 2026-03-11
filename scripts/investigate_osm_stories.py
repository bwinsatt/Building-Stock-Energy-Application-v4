"""
Investigate OSM building:levels and height tag coverage across US cities.

Queries Overpass API for buildings in downtown areas of major cities and
reports what percentage have building:levels, height, both, or neither.
"""
import json
import time
import requests

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

# Downtown coordinates for major US cities
CITIES = {
    "New York (Midtown)":    (40.7566, -73.9832),
    "New York (FiDi)":       (40.7074, -74.0113),
    "Chicago (Loop)":        (41.8819, -87.6278),
    "Los Angeles (DTLA)":    (34.0522, -118.2437),
    "Houston (Downtown)":    (29.7604, -95.3698),
    "Philadelphia (Center)": (39.9526, -75.1652),
    "Phoenix (Downtown)":    (33.4484, -112.0740),
    "San Francisco (FiDi)":  (37.7946, -122.3999),
    "Seattle (Downtown)":    (47.6062, -122.3321),
    "Denver (Downtown)":     (39.7392, -104.9903),
    "Boston (Downtown)":     (42.3601, -71.0589),
    "Atlanta (Downtown)":    (33.7490, -84.3880),
    "Miami (Downtown)":      (25.7617, -80.1918),
    "Washington DC":         (38.9007, -77.0369),
    "Dallas (Downtown)":     (32.7767, -96.7970),
}

TYPICAL_FLOOR_HEIGHT_M = 3.4


def query_city(name: str, lat: float, lon: float, radius: int = 300) -> dict:
    """Query OSM for buildings near a point and analyze tag coverage."""
    query = f"""
    [out:json][timeout:30];
    way["building"](around:{radius},{lat},{lon});
    out body;
    """
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    buildings = [e for e in data["elements"] if e["type"] == "way" and "building" in e.get("tags", {})]

    stats = {
        "total": len(buildings),
        "has_levels": 0,
        "has_height": 0,
        "has_both": 0,
        "has_neither": 0,
        "has_nycdoitt_bin": 0,
        "tall_no_levels": [],  # buildings with height > 30m but no levels
    }

    for b in buildings:
        tags = b.get("tags", {})
        has_levels = "building:levels" in tags
        has_height = "height" in tags

        if has_levels:
            stats["has_levels"] += 1
        if has_height:
            stats["has_height"] += 1
        if has_levels and has_height:
            stats["has_both"] += 1
        if not has_levels and not has_height:
            stats["has_neither"] += 1
        if "nycdoitt:bin" in tags:
            stats["has_nycdoitt_bin"] += 1

        # Track tall buildings missing levels
        if has_height and not has_levels:
            try:
                import re
                h = float(re.sub(r"[^\d.]", "", str(tags["height"])))
                if h > 30:
                    bname = tags.get("name", tags.get("addr:housenumber", f"way/{b['id']}"))
                    stats["tall_no_levels"].append(f"{bname} ({h}m ≈ {max(1,round(h/TYPICAL_FLOOR_HEIGHT_M))} floors)")
            except (ValueError, TypeError):
                pass

    return stats


def main():
    results = {}
    for city, (lat, lon) in CITIES.items():
        print(f"Querying {city}...", flush=True)
        try:
            stats = query_city(city, lat, lon)
            results[city] = stats
            time.sleep(2)  # be polite to Overpass
        except Exception as e:
            print(f"  ERROR: {e}")
            results[city] = {"error": str(e)}
            time.sleep(5)

    # Print report
    print("\n" + "=" * 90)
    print(f"{'City':<28} {'Total':>6} {'levels':>8} {'height':>8} {'both':>6} {'neither':>8} {'%levels':>8} {'%height':>8}")
    print("=" * 90)

    for city, s in results.items():
        if "error" in s:
            print(f"{city:<28} ERROR: {s['error']}")
            continue
        total = s["total"]
        if total == 0:
            print(f"{city:<28} No buildings found")
            continue
        pct_levels = s["has_levels"] / total * 100
        pct_height = s["has_height"] / total * 100
        print(f"{city:<28} {total:>6} {s['has_levels']:>8} {s['has_height']:>8} {s['has_both']:>6} {s['has_neither']:>8} {pct_levels:>7.1f}% {pct_height:>7.1f}%")
        if s["has_nycdoitt_bin"]:
            print(f"  └─ {s['has_nycdoitt_bin']} buildings have nycdoitt:bin tag")

    # Summary of tall buildings without levels
    print("\n" + "=" * 90)
    print("TALL BUILDINGS (>30m) WITH height BUT NO building:levels:")
    print("=" * 90)
    for city, s in results.items():
        if "error" in s:
            continue
        tall = s.get("tall_no_levels", [])
        if tall:
            print(f"\n{city}:")
            for t in tall[:5]:
                print(f"  • {t}")
            if len(tall) > 5:
                print(f"  ... and {len(tall)-5} more")


if __name__ == "__main__":
    main()
