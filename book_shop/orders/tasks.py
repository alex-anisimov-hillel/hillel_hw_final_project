import csv
import logging
from decimal import Decimal
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone

from books.models import Book
from orders.models import Order, OrderItem

logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 10
TOP_BOOKS_LIMIT = 5

REVENUE_STATUSES = [
    Order.OrderStatus.PAID,
    Order.OrderStatus.INWORK,
    Order.OrderStatus.SENT,
    Order.OrderStatus.DELIVERED,
]


def _reports_dir() -> Path:
    path = Path(getattr(settings, "REPORTS_DIR", Path(settings.BASE_DIR) / "reports"))
    path.mkdir(parents=True, exist_ok=True)
    return path


@shared_task
def generate_sales_report():
    now = timezone.now()
    orders_by_status = {
        row["status"]: row["count"]
        for row in Order.objects.values("status").annotate(count=Count("id"))
    }
    revenue = Order.objects.filter(status__in=REVENUE_STATUSES).aggregate(
        total=Sum("total_price")
    )["total"] or Decimal("0.00")
    top_books = list(
        OrderItem.objects.filter(order__status__in=REVENUE_STATUSES, book__isnull=False)
        .values("book_id", "book__title")
        .annotate(units=Sum("quantity"))
        .order_by("-units", "book__title")[:TOP_BOOKS_LIMIT]
    )
    low_stock = list(
        Book.objects.filter(stock__lt=LOW_STOCK_THRESHOLD)
        .order_by("stock", "title")
        .values("title", "stock")
    )

    report_path = _reports_dir() / f"sales_report_{now:%Y-%m-%d_%H%M%S}.csv"
    with report_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Sales report", now.isoformat()])
        writer.writerow([])
        writer.writerow(["Orders by status"])
        writer.writerow(["status", "orders"])
        for status, count in sorted(orders_by_status.items()):
            writer.writerow([status, count])
        writer.writerow([])
        writer.writerow(["Revenue (paid and later)", str(revenue)])
        writer.writerow([])
        writer.writerow([f"Top {TOP_BOOKS_LIMIT} books by units sold"])
        writer.writerow(["title", "units"])
        for row in top_books:
            writer.writerow([row["book__title"], row["units"]])
        writer.writerow([])
        writer.writerow([f"Low stock (< {LOW_STOCK_THRESHOLD})"])
        writer.writerow(["title", "stock"])
        for row in low_stock:
            writer.writerow([row["title"], row["stock"]])
    summary = {
        "report_path": str(report_path),
        "total_orders": sum(orders_by_status.values()),
        "revenue": str(revenue),
        "low_stock_books": len(low_stock),
    }
    logger.info("Sales report generated: %s", summary)
    return summary
