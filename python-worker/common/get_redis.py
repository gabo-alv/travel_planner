import os
import redis
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

@lru_cache(maxsize=1)
def get_redis():
    """
    Returns a singleton Redis connection per process.
    Safe for Temporal workers which may spawn multiple processes.
    """
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))

    return redis.Redis(
        host=host,
        port=port,
        db=0,
        decode_responses=True,   # return strings not bytes
    )