import json
import pickle
from functools import wraps

from redis import StrictRedis
from src.core.config import app_settings

redis_client = StrictRedis(
    host=app_settings.redis_host,
    port=app_settings.redis_port,
    db=app_settings.redis_db,
    password=app_settings.redis_password
)


def redis_cached_async(arg_slice: slice):
    def inner(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key_parts = [func.__name__] + list(map(str, args[arg_slice]))
            key = '-'.join(key_parts)
            result = redis_client.get(key)

            if result is None:
                value = await func(*args, **kwargs)

                value_binary = pickle.dumps(value)
                redis_client.set(key, value_binary)
            else:
                value_binary = result
                value = pickle.loads(value_binary)

            return value

        return wrapper

    return inner
