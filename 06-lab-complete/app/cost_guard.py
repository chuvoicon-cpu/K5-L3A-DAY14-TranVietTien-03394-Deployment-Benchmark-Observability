from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Nanodollars per estimated token at the lab's mock prices.
INPUT_PRICE = 150
OUTPUT_PRICE = 600
NANODOLLARS_PER_USD = 1_000_000_000


def check_budget() -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    day = now.date()
    key = f"day14:cost:{day.isoformat()}"
    spent = int(r.get(key) or 0)
    if spent >= settings.daily_budget_usd * NANODOLLARS_PER_USD:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")
    midnight = datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc)
    return key, int(midnight.timestamp())


def record_cost(input_tokens: int, output_tokens: int, period: tuple[str, int]) -> float:
    key, expires_at = period
    cost = input_tokens * INPUT_PRICE + output_tokens * OUTPUT_PRICE
    with r.pipeline() as transaction:
        transaction.incrby(key, cost)
        transaction.expireat(key, expires_at)
        transaction.execute()
    return cost / NANODOLLARS_PER_USD
