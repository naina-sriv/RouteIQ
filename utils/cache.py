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
            logger.warning(f"Redis unavailable ({e}). Caching disabled.")
            _redis_client = None
    return _redis_client


def _make_key(coords: list[tuple[float, float]]) -> str:
    payload = json.dumps(sorted(coords), separators=(",", ":"))
    return f"routeiq:matrix:{hashlib.md5(payload.encode()).hexdigest()}"


def get_matrix(coords: list[tuple[float, float]]) -> Optional[dict]:
    client = _get_client()
    if not client:
        return None
    try:
        raw = client.get(_make_key(coords))
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning(f"Cache get error: {e}")
        return None


def set_matrix(coords: list[tuple[float, float]], data: dict, ttl: int = 3600) -> None:
    client = _get_client()
    if not client:
        return
    try:
        client.setex(_make_key(coords), ttl, json.dumps(data))
    except Exception as e:
        logger.warning(f"Cache set error: {e}")
