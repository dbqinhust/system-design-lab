import os

from dotenv import load_dotenv
from pydantic import ValidationError
from redis import Redis
from redis.exceptions import RedisError

from app.schemas import URLRead


load_dotenv()

CACHE_TTL_SECONDS = int(os.getenv("REDIS_URL_TTL_SECONDS", "300"))
CACHE_ENABLED = os.getenv("REDIS_CACHE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

redis_client = Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
    socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "1")),
    socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "1")),
)


def _url_key(short_code: str) -> str:
    return f"urls:{short_code}"


def get_cached_url(short_code: str) -> URLRead | None:
    if not CACHE_ENABLED:
        return None
    try:
        value = redis_client.get(_url_key(short_code))
        return URLRead.model_validate_json(value) if value is not None else None
    except (RedisError, ValidationError):
        # Redis is an optimization; a cache problem must not block a DB lookup.
        return None


def cache_url(url: URLRead) -> None:
    if not CACHE_ENABLED:
        return
    try:
        redis_client.set(
            _url_key(url.short_code),
            url.model_dump_json(),
            ex=CACHE_TTL_SECONDS if CACHE_TTL_SECONDS > 0 else None,
        )
    except RedisError:
        pass


def invalidate_url(short_code: str) -> None:
    if not CACHE_ENABLED:
        return
    try:
        redis_client.delete(_url_key(short_code))
    except RedisError:
        pass
