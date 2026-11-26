"""Request correlation, security headers, Prometheus metrics and canary drills."""

from __future__ import annotations

import logging
import random
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from .config import Settings
from .metrics import IN_FLIGHT, LATENCY, REQUESTS
from .tracing import TraceContext

logger = logging.getLogger("taskflow.request")
SKIP_METRICS = {"/metrics", "/healthz", "/readyz"}


def route_label(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else "unmatched"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:  # noqa: ANN001
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)

        context = TraceContext.from_traceparent(request.headers.get("traceparent"))
        request.state.trace_id = context.trace_id
        request.state.request_id = context.request_id
        request.state.traceparent = context.traceparent
        started = time.perf_counter()
        IN_FLIGHT.inc()
        injected = (
            self.settings.failure_rate > 0
            and not self.settings.is_production
            and path.startswith("/api/v1/tasks")
            and random.random() < self.settings.failure_rate
        )
        status = 500
        try:
            if injected:
                response: Response = JSONResponse(
                    status_code=503,
                    content={
                        "detail": "Injected canary failure",
                        "request_id": context.request_id,
                    },
                )
                status = 503
            else:
                response = await call_next(request)
                status = response.status_code
            return self._decorate(request, response, context)
        except Exception:
            logger.exception(
                "request.failed",
                extra={"context": {"trace_id": context.trace_id, "path": path}},
            )
            raise
        finally:
            duration = time.perf_counter() - started
            label = route_label(request)
            if path not in SKIP_METRICS:
                REQUESTS.labels(request.method, label, str(status)).inc()
                LATENCY.labels(request.method, label).observe(duration)
                logger.info(
                    "request.complete",
                    extra={
                        "context": {
                            "trace_id": context.trace_id,
                            "request_id": context.request_id,
                            "method": request.method,
                            "route": label,
                            "status": status,
                            "duration_ms": round(duration * 1000, 2),
                            "client_ip": request.client.host if request.client else None,
                        }
                    },
                )
            IN_FLIGHT.dec()

    def _decorate(
        self,
        request: Request,
        response: Response,
        context: TraceContext,
    ) -> Response:
        headers = response.headers
        headers["X-Request-ID"] = context.request_id
        headers["X-Trace-ID"] = context.trace_id
        headers["traceparent"] = context.traceparent
        headers["X-Content-Type-Options"] = "nosniff"
        headers["Referrer-Policy"] = "no-referrer"
        headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        headers["Cache-Control"] = "no-store"
        csp = (
            "default-src 'self'; base-uri 'self'; form-action 'self'; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'"
        )
        if self.settings.is_production:
            csp += "; frame-ancestors 'none'"
            headers["X-Frame-Options"] = "DENY"
            if request.headers.get("x-forwarded-proto", request.url.scheme) == "https":
                headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        headers["Content-Security-Policy"] = csp
        return response
