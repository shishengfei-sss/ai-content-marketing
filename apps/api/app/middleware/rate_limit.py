"""简单按 IP+路径 的请求频率限制中间件。"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# path_prefix -> (max_requests, window_seconds)
LIMITS: dict[str, tuple[int, float]] = {
    "/api/v1/agent/health": (40, 60.0),
    "/api/v1/auth/login": (30, 60.0),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _limit_for(self, path: str) -> tuple[int, float] | None:
        for prefix, rule in LIMITS.items():
            if path == prefix or path.startswith(prefix + "/"):
                return rule
        return None

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        rule = self._limit_for(path)
        if rule is None:
            return await call_next(request)

        max_req, window = rule
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{path}"
        now = time.time()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= max_req:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请稍后重试"},
                )
            q.append(now)
        return await call_next(request)
