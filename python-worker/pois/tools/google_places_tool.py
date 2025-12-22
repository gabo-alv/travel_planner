# google_places_tool.py
import os
from typing import List, Optional
from pydantic import BaseModel, Field

import googlemaps


class DestinationPOI(BaseModel):
    id: str = Field(..., description="Google's placeId, unique identifier for the POI")
    name: str = Field(..., description="Display name of the point of interest")
    address: str = Field(..., description="Full formatted address of the POI")
    category: str = Field(..., description="Category or type of the POI")
    rating: Optional[float] = Field(ge=0, le=5, description="Average user rating from 0 to 5")
    user_ratings_total: Optional[int] = Field(ge=0, description="Total number of user ratings")
    lat: float
    lng: float
    description: Optional[str] = None
    url: Optional[str] = None
    photo_url: Optional[str] = None


def _photo_url(photo_ref: str, api_key: str) -> str:
    """Return Google Places photo URL."""
    return (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photo_reference={photo_ref}&key={api_key}"
    )


def _normalize_address(addr) -> str:
    if isinstance(addr, str):
        return addr.strip()
    if addr is None:
        return "Unknown address"
    return str(addr)


async def search_google_places(
    city: str,
    country: str = "",
    max_results: int = 10,
    poi_types: Optional[List[str]] = None,
    query: Optional[str] = None,
) -> List[DestinationPOI]:
    """
    REAL tourist-friendly destination research tool.
    Uses Google Places Text Search + Place Details.

    The agent can either:
    - provide a custom free-text `query`, OR
    - leave `query=None` and let us craft one from city/country/poi_types.
    """

    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY not set in environment")

    gmaps = googlemaps.Client(key=api_key)

    # Default tourist-friendly POI types
    if poi_types is None:
        poi_types = [
            "tourist_attraction",
            "museum",
            "historic",
            "landmark",
            "viewpoint",
            "park",
        ]

    # Build search query
    if query is None or not str(query).strip():
        # Heuristic: build something expressive but simple
        human_types = ", ".join(t.replace("_", " ") for t in poi_types)
        base = f"top {human_types} in {city}".strip()
        if country:
            base += f", {country}"
        query = base
    else:
        # If the agent gave a query but also a city/country, gently enrich it
        q = str(query).strip()
        # Don't duplicate if already mentions the city
        if city and city.lower() not in q.lower():
            q += f" in {city}"
        if country and country.lower() not in q.lower():
            q += f", {country}"
        query = q

    # Make the query (Text Search)
    resp = gmaps.places(query)

    if "results" not in resp or not resp["results"]:
        return []

    results = resp["results"][:max_results]
    pois: List[DestinationPOI] = []

    for res in results:
        place_id = res.get("place_id")
        if not place_id:
            continue

        # Fetch richer details using Place Details
        details = gmaps.place(
            place_id=place_id,
            fields=[
                "place_id",
                "name",
                "formatted_address",       # <- fixed spelling
                "geometry/location",
                "url",
                "editorial_summary",
                "rating",
                "user_ratings_total",
            ],
        )

        d = details.get("result", {})

        name = d.get("name")
        place_id = d.get("place_id")
        address = _normalize_address(d.get("formatted_address"))
        loc = d.get("geometry", {}).get("location", {})
        lat = loc.get("lat")
        lng = loc.get("lng")
        rating = d.get("rating")
        count = d.get("user_ratings_total")
        types = d.get("types", [])
        description = d.get("editorial_summary", {}).get("overview")
        url = d.get("url")

        # Filter if category not relevant
        category = next(
            (t for t in types if t in poi_types),
            types[0] if types else "poi",
        )

        photo_url = None
        photos = d.get("photos")
        if photos:
            ref = photos[0].get("photo_reference")
            if ref:
                photo_url = _photo_url(ref, api_key)

        poi = DestinationPOI(
            id=place_id,
            name=name,
            address=address,
            category=category,
            rating=rating,
            user_ratings_total=count,
            lat=lat,
            lng=lng,
            description=description,
            url=url,
            photo_url=photo_url,
        )
        pois.append(poi)

    return pois

