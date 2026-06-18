import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None


def _get_client():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            from config import REDIS_URL
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            _redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}. Caching disabled.")
            _redis_client = None
    return _redis_client


def _make_key(coords: list[tuple[float, float]]) -> str:
    """Stable cache key from sorted coordinate pairs."""
    sorted_coords = sorted(coords)
    payload = json.dumps(sorted_coords, separators=(",", ":"))
    return "routeiq:matrix:" + hashlib.md5(payload.encode()).hexdigest()


def get_matrix(coords: list[tuple[float, float]]) -> Optional[dict]:
    client = _get_client()
    if not client:
        return None
    try:
        key = _make_key(coords)
        raw = client.get(key)
        if raw:
            logger.debug(f"Cache HIT for key {key[:20]}…")
            return json.loads(raw)
        logger.debug(f"Cache MISS for key {key[:20]}…")
        return None
    except Exception as e:
        logger.warning(f"Cache get error: {e}")
        return None


def set_matrix(coords: list[tuple[float, float]], data: dict, ttl: int = 3600) -> None:
    client = _get_client()
    if not client:
        return
    try:
        key = _make_key(coords)
        client.setex(key, ttl, json.dumps(data))
        logger.debug(f"Cache SET for key {key[:20]}…")
    except Exception as e:
        logger.warning(f"Cache set error: {e}")
