import logging
import time
from collections.abc import Callable

from django.core.handlers.asgi import ASGIRequest
from django.http import HttpResponse

logger = logging.getLogger(__name__)


class AccessLogMiddleware:
    def __init__(self, get_response: Callable[[ASGIRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: ASGIRequest) -> HttpResponse:
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
        )
        return response
