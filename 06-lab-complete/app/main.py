import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.auth import verify_api_key
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask

logger = logging.getLogger("day14.agent")
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "lvl": "INFO",
        "event": event,
        **fields,
    }))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup")
    try:
        yield
    finally:
        r.close()
        log_event("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log_event(
            "request",
            path=request.url.path,
            method=request.method,
            status=status,
            ms=round((time.perf_counter() - start) * 1000, 1),
        )


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"ready": True}


@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    period = check_budget()
    answer = llm_ask(body.question)
    cost = record_cost(len(body.question.split()) * 2, len(answer.split()) * 2, period)
    return {"question": body.question, "answer": answer, "cost_usd": cost}
