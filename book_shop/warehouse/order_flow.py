"""Order <-> warehouse reservation flow.

Rules of the road
-----------------
* ``Order.reservation_status`` records where we are; every function is idempotent
  (the warehouse keys reservations by order id), so tasks/commands can be re-run safely.
* Order rows are updated with ``QuerySet.update`` so these status bookkeeping writes do
  not re-fire the Order ``post_save`` signal.
* Warehouse downtime never loses an order: it is kept as ``pending_retry`` and a Celery
  task retries with backoff (plus a periodic safety-net task).
"""

import logging

from django.conf import settings

from orders.models import Order
from warehouse.client import WarehouseClient
from warehouse.exceptions import (
    InsufficientStock,
    ReservationConflict,
    WarehouseUnavailable,
)

logger = logging.getLogger("orders.warehouse")

RS = Order.ReservationStatus


def _set(order_id, **fields):
    Order.objects.filter(pk=order_id).update(**fields)


def _schedule_retry(order_id):
    from warehouse.tasks import reserve_order_stock_task

    try:
        reserve_order_stock_task.apply_async(args=[order_id], countdown=30)
    except Exception:  # broker down: the periodic task is the safety net
        logger.exception("Could not schedule reservation retry for order %s", order_id)


def reserve_order_stock(order_id, *, retry_via_celery=True) -> str:
    """Reserve the order's books in the warehouse; return the new reservation status.

    Raises ``InsufficientStock`` (after cancelling the order) when stock is short.
    If the warehouse is unreachable: with ``retry_via_celery`` the order is parked as
    ``pending_retry`` and a retry is scheduled; otherwise ``WarehouseUnavailable`` is
    raised so the calling Celery task can use its own retry policy.
    """
    if not settings.WAREHOUSE_ENABLED:
        return RS.NONE
    order = Order.objects.prefetch_related("books").get(pk=order_id)
    if order.reservation_status in (RS.RESERVED, RS.CONFIRMED):
        return order.reservation_status
    items = [
        {"book_id": line.book_id, "quantity": line.quantity}
        for line in order.books.all()
        if line.book_id
    ]
    if not items:
        return order.reservation_status

    try:
        reservation = WarehouseClient().reserve(order.pk, items)
    except InsufficientStock:
        _set(order.pk, status=Order.OrderStatus.CANCELED, reservation_status=RS.FAILED)
        logger.warning("Order %s cancelled: not enough stock", order.pk)
        raise
    except WarehouseUnavailable:
        _set(order.pk, reservation_status=RS.PENDING_RETRY)
        logger.warning(
            "Warehouse unavailable: order %s kept as pending_retry", order.pk
        )
        if retry_via_celery:
            _schedule_retry(order.pk)
            return RS.PENDING_RETRY
        raise
    _set(order.pk, reservation_id=reservation["id"], reservation_status=RS.RESERVED)
    logger.info("Order %s reserved in warehouse (%s)", order.pk, reservation["id"])
    return RS.RESERVED


def confirm_order_reservation(order_id) -> str:
    """Order is paid: make the reservation final (stock leaves the warehouse)."""
    order = Order.objects.get(pk=order_id)
    if order.reservation_status == RS.PENDING_RETRY:
        # Paid while the warehouse was down: place the reservation first.
        reserve_order_stock(order_id, retry_via_celery=False)
        order.refresh_from_db()
    if order.reservation_status != RS.RESERVED or not order.reservation_id:
        return order.reservation_status
    try:
        WarehouseClient().confirm(order.reservation_id)
    except ReservationConflict:
        # e.g. the customer paid after the reservation expired and stock was released.
        _set(order.pk, reservation_status=RS.FAILED)
        logger.error(
            "PAID order %s: warehouse refused to confirm reservation %s "
            "- needs manual handling",
            order.pk,
            order.reservation_id,
        )
        return RS.FAILED
    _set(order.pk, reservation_status=RS.CONFIRMED)
    logger.info("Order %s: reservation confirmed", order.pk)
    return RS.CONFIRMED


def cancel_order_reservation(order_id) -> str:
    """Order cancelled: give the reserved stock back."""
    order = Order.objects.get(pk=order_id)
    if order.reservation_status not in (RS.RESERVED, RS.PENDING_RETRY):
        return order.reservation_status
    client = WarehouseClient()
    reservation_id = order.reservation_id
    if not reservation_id:
        # We may have lost the reply to a reserve call that actually succeeded.
        found = client.find_reservation(order.pk)
        reservation_id = found["id"] if found else None
    if reservation_id:
        try:
            client.cancel(reservation_id)
        except ReservationConflict:
            logger.error(
                "Order %s cancelled but reservation %s is already shipped",
                order.pk,
                reservation_id,
            )
    _set(order.pk, reservation_status=RS.RELEASED)
    logger.info("Order %s: reservation released", order.pk)
    return RS.RELEASED
