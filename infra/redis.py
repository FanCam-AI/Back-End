import redis.asyncio as redis
from config import settings

def get_redis_client():
    redis_client = redis.Redis(
        host=settings.REDIS_CLOUD_HOST,
        port=19268,
        decode_responses=True,
        username="default",
        password=settings.REDIS_CLOUD_PASSWORD,
    )

    return redis_client


redis_client = get_redis_client()