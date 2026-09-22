import logging
import time

from django.core.handlers.asgi import ASGIRequest

logger = logging.getLogger(__name__)


class AccessLogMiddleware:
    def __init__(self, get_response) -> None:  # noqa: ANN001
        self.get_response = get_response

    def __call__(self, request: ASGIRequest):  # noqa: ANN204
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
