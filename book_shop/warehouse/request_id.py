"""Request-ID propagation: one correlation id per request, visible in every log line.

Every outgoing call to the warehouse service carries the current id in ``X-Request-ID``
so one order can be traced through both services' logs (the warehouse reuses it).
"""

import contextvars
import logging
import re
import uuid

HEADER = "X-Request-ID"
_META_KEY = "HTTP_X_REQUEST_ID"
_VALID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")  # also prevents log injection

request_id_var = contextvars.ContextVar("request_id", default="-")


def get_request_id() -> str:
    return request_id_var.get()


def new_request_id() -> str:
    return uuid.uuid4().hex


class RequestIDFilter(logging.Filter):
    """Adds ``record.request_id`` so formatters can use ``%(request_id)s``."""

    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(_META_KEY, "")
        request_id = incoming if _VALID.match(incoming) else new_request_id()
        token = request_id_var.set(request_id)
        request.request_id = request_id
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[HEADER] = request_id
        return response


def connect_celery_signals():
    """Give every Celery task its own request id (``task-<id>``) for log correlation."""
    from celery.signals import task_postrun, task_prerun

    tokens = {}

    @task_prerun.connect(weak=False)
    def _bind(task_id=None, **kwargs):
        tokens[task_id] = request_id_var.set(f"task-{task_id[:8]}")

    @task_postrun.connect(weak=False)
    def _unbind(task_id=None, **kwargs):
        token = tokens.pop(task_id, None)
        if token is not None:
            request_id_var.reset(token)
