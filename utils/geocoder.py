import httpx
import logging

logger = logging.getLogger(__name__)

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
HEADERS = {"User-Agent": "RouteIQ/2.0 (route-optimizer)"}


async def geocode(query: str) -> dict:
    url = f"{NOMINATIM_BASE}/search"
    params = {"q": query, "format": "json", "limit": 1}
    async with httpx.AsyncClient(timeout=10.0, headers=HEADERS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"No geocoding results for: {query!r}")
    r = results[0]
    return {"lat": float(r["lat"]), "lng": float(r["lon"]), "display_name": r["display_name"]}


async def reverse_geocode(lat: float, lng: float) -> str:
    url = f"{NOMINATIM_BASE}/reverse"
    params = {"lat": lat, "lon": lng, "format": "json"}
    async with httpx.AsyncClient(timeout=10.0, headers=HEADERS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
    data = resp.json()
    return data.get("display_name", f"{lat:.5f}, {lng:.5f}")
