import logging
import httpx
from config import POSITION_STACK_API_KEY

logger = logging.getLogger(__name__)

POSITION_STACK_BASE = "http://api.positionstack.com/v1"
HEADERS = {"User-Agent": "RouteIQ/2.0 (route-optimizer)"}
TIMEOUT = 10.0


async def geocode(query: str) -> dict:
    if not POSITION_STACK_API_KEY:
        raise ValueError("POSITION_STACK_API_KEY is not set. Please set it in your .env file.")

    url = f"{POSITION_STACK_BASE}/forward"
    params = {"access_key": POSITION_STACK_API_KEY, "query": query, "limit": 1}

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    data = resp.json().get("data")
    if not data:
        raise ValueError(f"No geocoding results for: {query!r}")

    result = data[0]
    return {"lat": float(result["latitude"]), "lng": float(result["longitude"]), "display_name": result.get("label") or result.get("name") or query}


async def reverse_geocode(lat: float, lng: float) -> str:
    fallback = f"{lat:.5f}, {lng:.5f}"
    if not POSITION_STACK_API_KEY:
        return fallback

    url = f"{POSITION_STACK_BASE}/reverse"
    params = {"access_key": POSITION_STACK_API_KEY, "query": f"{lat},{lng}", "limit": 1}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json().get("data")
                if data:
                    return data[0].get("label") or data[0].get("name") or fallback
    except Exception as e:
        logger.warning(f"Reverse geocode failed ({e}), using fallback")

    return fallback
