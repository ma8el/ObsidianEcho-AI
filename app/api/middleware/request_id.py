"""Request ID middleware."""

import time
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.logging import get_logger
from app.core.security import generate_request_id

logger = get_logger(__name__)

# Context variable for request ID (accessible throughout request lifecycle)
request_id_context: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request ID to all requests and responses.

    Generates a unique request ID for each request and adds it to:
    - Response headers (X-Request-ID)
    - Logging context
    - Request state (accessible via request.state.request_id)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process request and add request ID.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response with X-Request-ID header
        """
        # Generate or use provided request ID
        req_id = request.headers.get("X-Request-ID", generate_request_id())

        # Store in request state
        request.state.request_id = req_id

        # Store in context variable for logging
        request_id_context.set(req_id)

        # Log request
        start_time = time.time()
        logger.info(
            "Request started",
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log error with request ID
            logger.error(
                "Request failed with exception",
                extra={
                    "request_id": req_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Add request ID to response headers
        response.headers["X-Request-ID"] = req_id

        # Log response
        logger.info(
            "Request completed",
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return response


def get_request_id() -> str:
    """
    Get the current request ID from context.

    Returns:
        Current request ID or empty string if not in request context
    """
    return request_id_context.get()
