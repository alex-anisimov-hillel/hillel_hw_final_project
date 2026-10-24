import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _


def default_low_stock_threshold():
    return settings.DEFAULT_LOW_STOCK_THRESHOLD


class Warehouse(models.Model):
    name = models.CharField(max_length=120, verbose_name=_("Name"))
    code = models.SlugField(max_length=30, unique=True, verbose_name=_("Code"))
    address = models.CharField(max_length=255, blank=True, verbose_name=_("Address"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    priority = models.PositiveSmallIntegerField(
        default=100,
        verbose_name=_("Priority"),
        help_text=_("Lower value = used first when allocating stock."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "code"]
        verbose_name = _("Warehouse")
        verbose_name_plural = _("Warehouses")

    def __str__(self):
        return f"{self.name} ({self.code})"


class StockItem(models.Model):
    """Stock of one book (identified by ProjectA's Book id) in one warehouse."""

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="items",
        verbose_name=_("Warehouse"),
    )
    book_id = models.PositiveIntegerField(db_index=True, verbose_name=_("Book ID"))
    title = models.CharField(max_length=200, blank=True, verbose_name=_("Title"))
    isbn = models.CharField(max_length=20, blank=True, verbose_name=_("ISBN"))
    quantity = models.PositiveIntegerField(default=0, verbose_name=_("On hand"))
    reserved = models.PositiveIntegerField(default=0, verbose_name=_("Reserved"))
    low_stock_threshold = models.PositiveIntegerField(
        default=default_low_stock_threshold, verbose_name=_("Low stock threshold")
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Stock item")
        verbose_name_plural = _("Stock items")
        ordering = ["book_id", "warehouse__priority"]
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "book_id"], name="uniq_book_per_warehouse"
            ),
            models.CheckConstraint(
                condition=Q(reserved__lte=F("quantity")), name="reserved_lte_quantity"
            ),
        ]
        permissions = [
            ("restock_stockitem", "Can add stock (restock)"),
            ("adjust_stockitem", "Can correct stock (adjust)"),
            ("manage_reservation", "Can reserve, confirm and cancel reservations"),
        ]

    def __str__(self):
        return f"book #{self.book_id} @ {self.warehouse.code}: {self.available}"

    @property
    def available(self) -> int:
        return self.quantity - self.reserved


class StockReservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        CONFIRMED = "confirmed", _("Confirmed")
        CANCELLED = "cancelled", _("Cancelled")
        EXPIRED = "expired", _("Expired")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # ProjectA's order id. Unique => POST /reservations/ is idempotent per order.
    order_id = models.PositiveIntegerField(unique=True, verbose_name=_("Order ID"))
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_("Status"),
    )
    expires_at = models.DateTimeField(verbose_name=_("Expires at"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Stock reservation")
        verbose_name_plural = _("Stock reservations")

    def __str__(self):
        return f"order #{self.order_id} [{self.status}]"


class ReservationLine(models.Model):
    reservation = models.ForeignKey(
        StockReservation, on_delete=models.CASCADE, related_name="lines"
    )
    stock_item = models.ForeignKey(
        StockItem, on_delete=models.PROTECT, related_name="+"
    )
    book_id = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity} x book #{self.book_id}"


class StockMovement(models.Model):
    """Append-only ledger: every change of ``quantity``/``reserved`` is recorded."""

    class Kind(models.TextChoices):
        RESTOCK = "restock", _("Restock")
        RESERVE = "reserve", _("Reserve")
        RELEASE = "release", _("Release")
        SHIP = "ship", _("Ship")
        ADJUST = "adjust", _("Adjustment")

    stock_item = models.ForeignKey(
        StockItem, on_delete=models.PROTECT, related_name="movements"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, verbose_name=_("Kind"))
    quantity_delta = models.IntegerField(default=0, verbose_name=_("On hand change"))
    reserved_delta = models.IntegerField(default=0, verbose_name=_("Reserved change"))
    reservation = models.ForeignKey(
        StockReservation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name=_("Note"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = _("Stock movement")
        verbose_name_plural = _("Stock movements")

    def __str__(self):
        return f"{self.kind} {self.quantity_delta:+d}/{self.reserved_delta:+d}"
