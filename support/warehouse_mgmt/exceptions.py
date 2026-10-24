"""Domain errors (all are DRF ``APIException`` so they map to proper HTTP responses)."""

import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from support.request_id import get_request_id

logger = logging.getLogger(__name__)


class InsufficientStock(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "insufficient_stock"
    default_detail = _("Not enough stock to fulfil the request.")

    def __init__(self, shortages):
        # shortages: [{"book_id": 1, "requested": 5, "available": 2}, ...]
        super().__init__(detail=self.default_detail)
        # APIException stringifies nested values (ints -> "1"); keep numbers numeric.
        self.detail = {
            "detail": self.detail,
            "code": self.default_code,
            "shortages": shortages,
        }
        self.shortages = shortages


class ReservationStateError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "invalid_reservation_state"
    default_detail = _("The reservation is in a state that does not allow this action.")


class InvalidAdjustment(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_adjustment"
    default_detail = _(
        "The adjustment would make stock negative or below the reserved amount."
    )


class UnknownWarehouse(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "unknown_warehouse"
    default_detail = _("Warehouse not found or inactive.")


_FALLBACK_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    429: "throttled",
}


def api_exception_handler(exc, context):
    """DRF handler: one JSON error shape for everything, never a raw 500 page.

    Shape: ``{"detail": ..., "code": ..., "request_id": ...}`` (+ ``errors`` for
    validation problems, ``shortages`` for insufficient stock).
    """
    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled error in %s", context.get("view"))
        return Response(
            {
                "detail": _("Internal server error."),
                "code": "server_error",
                "request_id": get_request_id(),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Build a new body: response.data may be the exception's own ``detail`` object.
    if isinstance(exc, ValidationError):
        body = {
            "detail": _("Invalid input."),
            "code": "validation_error",
            "errors": response.data,
        }
    elif isinstance(response.data, dict):
        body = dict(response.data)
        if "code" not in body:
            codes = exc.get_codes() if hasattr(exc, "get_codes") else None
            body["code"] = (
                codes
                if isinstance(codes, str)
                else _FALLBACK_CODES.get(response.status_code, "error")
            )
    else:
        body = {"detail": response.data, "code": "error"}
    body["request_id"] = get_request_id()
    response.data = body
    return response
