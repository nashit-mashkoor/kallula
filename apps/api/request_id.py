import logging
from contextvars import ContextVar, Token
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("api.request")


def get_request_id() -> str | None:
    return request_id_var.get()


def set_request_id(request_id: str) -> Token[str | None]:
    return request_id_var.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_var.reset(token)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        token = set_request_id(request_id)
        start = perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((perf_counter() - start) * 1000, 2)
            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)
