"""Errors raised by :class:`warehouse.client.WarehouseClient`.

Callers only need to distinguish three situations:

* ``WarehouseUnavailable`` - temporary (network, timeout, 5xx): retry later and
  degrade gracefully;
* ``InsufficientStock`` - business answer "no": tell the customer;
* everything else (``WarehouseError`` subclasses) - a bug/misconfiguration: log loudly.
"""


class WarehouseError(Exception):
    """Base class for all warehouse-integration errors."""


class WarehouseUnavailable(WarehouseError):
    """Warehouse could not be reached or answered with a temporary error."""


class WarehouseAuthError(WarehouseError):
    """Service-account credentials were rejected (misconfiguration)."""


class WarehouseBadRequest(WarehouseError):
    """The warehouse rejected our request as invalid (HTTP 400/404)."""

    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = payload or {}


class ReservationConflict(WarehouseError):
    """Reservation is in a state that forbids the action (e.g. confirm after expiry)."""


class InsufficientStock(WarehouseError):
    """Not enough stock; ``shortages``: ``[{"book_id", "requested", "available"}]``."""

    def __init__(self, shortages):
        super().__init__(f"Insufficient stock: {shortages}")
        self.shortages = shortages
