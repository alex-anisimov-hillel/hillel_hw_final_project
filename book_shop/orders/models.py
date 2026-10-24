from django.db import models
from users.models import User
from books.models import Book

from django.utils.translation import gettext_lazy as _


class Order(models.Model):
    class OrderStatus(models.TextChoices):
        CREATED = "created", "Created"
        PAID = "paid", "Paid"
        INWORK = "in work", "In work"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        CANCELED = "canceled", "Canceled"

    class ReservationStatus(models.TextChoices):
        """State of the stock reservation held in the warehouse service (ProjectB)."""

        NONE = "none", "Not tracked"
        RESERVED = "reserved", "Reserved"
        PENDING_RETRY = "pending_retry", "Waiting for warehouse"
        CONFIRMED = "confirmed", "Confirmed"
        RELEASED = "released", "Released"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, verbose_name=_("User")
    )
    email = models.EmailField(null=True, blank=True, verbose_name=_("Email"))
    phone_number = models.CharField(
        max_length=20, null=True, blank=True, verbose_name=_("Phone number")
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name=_("Address")
    )
    city = models.CharField(
        max_length=200, null=True, blank=True, verbose_name=_("City")
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.CREATED,
        verbose_name=_("Status"),
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Total price")
    )
    payment_method = models.OneToOneField(
        "payment.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Payment method"),
    )
    reservation_id = models.UUIDField(
        null=True, blank=True, editable=False, verbose_name=_("Warehouse reservation")
    )
    reservation_status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.NONE,
        db_index=True,
        verbose_name=_("Reservation status"),
    )

    def __str__(self):
        return f"{self.user} -- {self.status}"

    class Meta:
        verbose_name_plural = _("Orders")


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="books",
        null=True,
        blank=True,
        verbose_name=_("Order"),
    )
    book = models.ForeignKey(
        Book, on_delete=models.PROTECT, null=True, blank=True, verbose_name=_("Book")
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Price")
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name=_("Quantity"))

    def get_total(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.order} -- {self.book} -- {self.price}"
