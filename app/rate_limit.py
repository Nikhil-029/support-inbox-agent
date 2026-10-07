import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

MAX_FETCHES_PER_HOUR = int(os.getenv("DEMO_MAX_FETCHES_PER_HOUR", "20"))
WINDOW_SECONDS = 3600

_hits: dict = defaultdict(deque)


def enforce_fetch_rate_limit(request: Request) -> None:
    if os.getenv("DEMO_MODE", "false").lower() != "true":
        return

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _hits[client_ip]

    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= MAX_FETCHES_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=f"Demo limit reached ({MAX_FETCHES_PER_HOUR} fetches/hour per visitor).",
        )
    bucket.append(now)
