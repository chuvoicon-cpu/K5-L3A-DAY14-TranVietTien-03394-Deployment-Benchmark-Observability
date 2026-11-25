from uuid import uuid4

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Redis supplies a shared clock and executes the entire sliding window atomically.
take_slot = r.register_script("""
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return math.max(1, math.ceil(60 - (now - tonumber(oldest[2]))))
end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('EXPIRE', KEYS[1], 60)
return 0
""")


def check_rate_limit(key: str) -> None:
    retry_after = take_slot(
        keys=[f"day14:rate:{key}"],
        args=[settings.rate_limit_per_minute, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
