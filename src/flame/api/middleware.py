"""HTTP middleware for request correlation, structured access logging, and timing."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from flame.observability.logging import reset_request_id, set_request_id

logger = logging.getLogger("flame.api.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns request correlation ID and logs structured HTTP access telemetry."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        req_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        token = set_request_id(req_id)
        start_time = time.monotonic()

        try:
            response = await call_next(request)
            duration_ms = (time.monotonic() - start_time) * 1000.0
            response.headers["x-request-id"] = req_id

            logger.info(
                "%s %s -> %s (%.2fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        except Exception:
            duration_ms = (time.monotonic() - start_time) * 1000.0
            logger.exception(
                "Unhandled error during request %s %s (%.2fms)",
                request.method,
                request.url.path,
                duration_ms,
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            reset_request_id(token)


__all__ = ["RequestContextMiddleware"]
