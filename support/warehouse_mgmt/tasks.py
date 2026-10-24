import csv
import logging
import uuid
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from warehouse_mgmt import services
from warehouse_mgmt.models import StockItem, StockReservation
from warehouse_mgmt.webhooks import WebhookDeliveryError, deliver

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(WebhookDeliveryError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": 6},
)
def send_webhook(event, data, event_id=None):
    """Deliver one signed webhook to ProjectA, retrying temporary failures."""
    return deliver(event, data, event_id)


@shared_task
def notify_stock_changed(book_ids):
    """Push fresh availability for ``book_ids`` to ProjectA (it mirrors Book.stock)."""
    availability = services.get_availability(book_ids, use_cache=False)
    data = {
        "items": [
            {
                "book_id": b,
                "available": v["available"],
                "quantity": v["quantity"],
                "reserved": v["reserved"],
            }
            for b, v in availability.items()
        ]
    }
    send_webhook.delay("stock.changed", data, uuid.uuid4().hex)
    return len(data["items"])


@shared_task
def expire_stale_reservations(batch_size=500):
    """Release stock held by unpaid reservations whose TTL has run out."""
    ids = list(
        StockReservation.objects.filter(
            status=StockReservation.Status.PENDING, expires_at__lte=timezone.now()
        ).values_list("pk", flat=True)[:batch_size]
    )
    expired = 0
    for pk in ids:
        try:
            result = services.expire_reservation(pk)
            expired += result.status == StockReservation.Status.EXPIRED
        except Exception:
            logger.exception("Could not expire reservation %s", pk)
    if expired:
        logger.info("Expired %s stale reservations", expired)
    return {"expired": expired}


@shared_task
def check_low_stock():
    """Warn (log + webhook) about items at or below their low-stock threshold."""
    items = [
        {
            "book_id": i.book_id,
            "title": i.title,
            "warehouse": i.warehouse.code,
            "available": i.avail,
            "threshold": i.low_stock_threshold,
        }
        for i in services.low_stock_items()
    ]
    if items:
        logger.warning("Low stock for %s item(s)", len(items))
        send_webhook.delay("stock.low", {"items": items}, uuid.uuid4().hex)
    return {"low_stock_items": len(items)}


@shared_task
def generate_stock_report():
    """Write reports/stock_report_<timestamp>.csv with the current stock levels."""
    now = timezone.now()
    reports_dir = Path(settings.REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"stock_report_{now:%Y-%m-%d_%H%M%S}.csv"
    rows = StockItem.objects.select_related("warehouse").order_by(
        "book_id", "warehouse__code"
    )
    count = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Stock report", now.isoformat()])
        writer.writerow(
            ["warehouse", "book_id", "title", "on_hand", "reserved", "available"]
        )
        for item in rows:
            writer.writerow(
                [
                    item.warehouse.code,
                    item.book_id,
                    item.title,
                    item.quantity,
                    item.reserved,
                    item.available,
                ]
            )
            count += 1
    logger.info("Stock report written: %s (%s rows)", path, count)
    return {"report_path": str(path), "rows": count}
