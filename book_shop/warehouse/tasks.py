import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import gettext as _

from books.models import Book
from orders.models import Order
from warehouse import order_flow
from warehouse.client import WarehouseClient
from warehouse.exceptions import InsufficientStock, WarehouseUnavailable

logger = logging.getLogger("orders.warehouse")

# Temporary warehouse failures are retried with exponential backoff (max ~1 hour total).
RETRY_POLICY = dict(
    autoretry_for=(WarehouseUnavailable,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 8},
)


@shared_task(**RETRY_POLICY)
def reserve_order_stock_task(order_id):
    try:
        return order_flow.reserve_order_stock(order_id, retry_via_celery=False)
    except InsufficientStock as exc:
        _notify_customer_out_of_stock(order_id, exc.shortages)
        return "failed"


@shared_task(**RETRY_POLICY)
def confirm_order_reservation_task(order_id):
    try:
        return order_flow.confirm_order_reservation(order_id)
    except InsufficientStock:
        logger.error(
            "PAID order %s could not be reserved (out of stock) - refund needed",
            order_id,
        )
        return "failed"


@shared_task(**RETRY_POLICY)
def cancel_order_reservation_task(order_id):
    return order_flow.cancel_order_reservation(order_id)


@shared_task
def retry_pending_reservations():
    """Safety net: re-enqueue orders still waiting for a warehouse reservation."""
    ids = list(
        Order.objects.filter(
            reservation_status=Order.ReservationStatus.PENDING_RETRY,
            status=Order.OrderStatus.CREATED,
        ).values_list("pk", flat=True)
    )
    for order_id in ids:
        reserve_order_stock_task.delay(order_id)
    return {"requeued": len(ids)}


def apply_stock_levels(levels):
    """Mirror warehouse availability into ``Book.stock`` (``{book_id: available}``)."""
    changed = 0
    for book in Book.objects.filter(pk__in=levels):
        available = levels[book.pk]
        if book.stock != available:
            book.stock = available
            book.save(
                update_fields=["stock"]
            )  # post_save signal drops the book's cache
            changed += 1
    return changed


@shared_task(**RETRY_POLICY)
def sync_stock_levels(chunk_size=200):
    """Pull availability for every book (reconciliation; webhooks are real-time)."""
    if not settings.WAREHOUSE_ENABLED:
        return {"skipped": True}
    client = WarehouseClient()
    ids = list(Book.objects.values_list("pk", flat=True))
    changed = 0
    for start in range(0, len(ids), chunk_size):
        availability = client.get_availability(ids[start : start + chunk_size])
        changed += apply_stock_levels(
            {b: v["available"] for b, v in availability.items() if v["tracked"]}
        )
    logger.info("Stock sync finished: %s of %s books updated", changed, len(ids))
    return {"books": len(ids), "changed": changed}


def _notify_customer_out_of_stock(order_id, shortages):
    order = Order.objects.filter(pk=order_id).first()
    if not order or not order.email:
        return
    send_mail(
        subject=_("Your order could not be fulfilled"),
        message=_(
            "Sorry, order #%(order_id)s was cancelled because some books ran out "
            "of stock."
        )
        % {"order_id": order_id},
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email],
        fail_silently=True,
    )
