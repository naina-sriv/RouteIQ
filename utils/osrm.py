import logging
import math
from typing import Optional
import httpx
from config import OSRM_BASE
from utils.cache import get_matrix, set_matrix

logger = logging.getLogger(__name__)

EARTH_RADIUS = 6_371_000
SPEED_MPS = 50.0 * (1000 / 3600)  # ~13.89 m/s (50 km/h)
OSRM_TIMEOUT = 10.0


def _haversine_seconds(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """Estimated travel time in seconds assuming 50 km/h average speed."""
    p1, p2, dlat, dlng = math.radians(lat1), math.radians(lat2), math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return int((2 * EARTH_RADIUS * math.asin(math.sqrt(a))) / SPEED_MPS)


def _straight_polyline(lat1: float, lng1: float, lat2: float, lng2: float) -> list[list[float]]:
    return [[lat1, lng1], [lat2, lng2]]


async def get_distance_matrix(coords: list[tuple[float, float]]) -> tuple[list[list[int]], bool]:
    cached = get_matrix(coords)
    if cached:
        return cached["matrix"], cached.get("used_fallback", False)

    try:
        matrix = await _osrm_matrix(coords)
        set_matrix(coords, {"matrix": matrix, "used_fallback": False})
        return matrix, False
    except Exception as e:
        logger.warning(f"OSRM matrix failed ({e}), using haversine fallback")
        return _haversine_matrix(coords), True


async def _osrm_matrix(coords: list[tuple[float, float]]) -> list[list[int]]:
    url = f"{OSRM_BASE}/table/v1/driving/{';'.join(f'{lng},{lat}' for lat, lng in coords)}?annotations=duration"
    async with httpx.AsyncClient(timeout=OSRM_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    data = resp.json()
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM error: {data.get('code')}")
    return [[int(d) if d is not None else 10**6 for d in row] for row in data["durations"]]


def _haversine_matrix(coords: list[tuple[float, float]]) -> list[list[int]]:
    n = len(coords)
    return [[0 if i == j else _haversine_seconds(coords[i][0], coords[i][1], coords[j][0], coords[j][1]) for j in range(n)] for i in range(n)]


async def get_route_polyline(lat1: float, lng1: float, lat2: float, lng2: float) -> tuple[list[list[float]], bool]:
    try:
        url = f"{OSRM_BASE}/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson"
        async with httpx.AsyncClient(timeout=OSRM_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        data = resp.json()
        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM route error: {data.get('code')}")
        return [[c[1], c[0]] for c in data["routes"][0]["geometry"]["coordinates"]], False
    except Exception as e:
        logger.warning(f"OSRM route polyline failed ({e}), using straight line")
        return _straight_polyline(lat1, lng1, lat2, lng2), True
