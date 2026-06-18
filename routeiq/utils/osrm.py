import math
import logging
from typing import Optional
import httpx
from config import OSRM_BASE
from utils.cache import get_matrix, set_matrix

logger = logging.getLogger(__name__)

OSRM_TIMEOUT = 10.0



def _haversine_seconds(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """Straight-line distance in seconds at ~50 km/h average."""
    R = 6371000

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    metres = 2 * R * math.asin(math.sqrt(a))
    return int(metres / (50_000 / 3600))



def _straight_polyline(lat1: float, lng1: float, lat2: float, lng2: float) -> list[list[float]]:
    return [[lat1, lng1], [lat2, lng2]]


async def get_distance_matrix(coords: list[tuple[float, float]]) -> tuple[list[list[int]], bool]:
    """
    Returns (matrix_seconds, used_fallback).
    Checks Redis cache first, then OSRM, then haversine fallback.
    """
    cached = get_matrix(coords)
    if cached:
        return cached["matrix"], cached.get("used_fallback", False)

    try:
        result = await _osrm_matrix(coords)
        set_matrix(coords, {"matrix": result, "used_fallback": False})
        return result, False
    except Exception as e:
        logger.warning(f"OSRM matrix failed ({e}), using haversine fallback")
        result = _haversine_matrix(coords)

        return result, True


async def _osrm_matrix(coords: list[tuple[float, float]]) -> list[list[int]]:
    """Fetch real-road travel-time matrix from OSRM."""
    coord_str = ";".join(f"{lng},{lat}" for lat, lng in coords)
    url = f"{OSRM_BASE}/table/v1/driving/{coord_str}?annotations=duration"
    async with httpx.AsyncClient(timeout=OSRM_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM error: {data.get('code')}")
    durations = data["durations"]
    return [[int(d) if d is not None else 10**6 for d in row] for row in durations]


def _haversine_matrix(coords: list[tuple[float, float]]) -> list[list[int]]:
    n = len(coords)
    return [
        [
            0 if i == j else _haversine_seconds(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            for j in range(n)
        ]
        for i in range(n)
    ]


async def get_route_polyline(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> tuple[list[list[float]], bool]:
    """Returns (polyline_points, used_fallback)."""
    try:
        url = f"{OSRM_BASE}/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson"
        async with httpx.AsyncClient(timeout=OSRM_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM route error: {data.get('code')}")
        coords = data["routes"][0]["geometry"]["coordinates"]

        return [[c[1], c[0]] for c in coords], False
    except Exception as e:
        logger.warning(f"OSRM route polyline failed ({e}), using straight line")
        return _straight_polyline(lat1, lng1, lat2, lng2), True
