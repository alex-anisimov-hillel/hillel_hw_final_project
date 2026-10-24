from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order

DONE = {
    Order.ReservationStatus.NONE,
    Order.ReservationStatus.CONFIRMED,
    Order.ReservationStatus.RELEASED,
    Order.ReservationStatus.FAILED,
}


@receiver(post_save, sender=Order)
def sync_reservation_with_order(sender, instance, created, raw=False, **kwargs):
    """Paid -> confirm the reservation, cancelled -> release it (asynchronously)."""
    if raw or created or not settings.WAREHOUSE_ENABLED:
        return
    if instance.reservation_status in DONE:
        return
    from warehouse.tasks import (
        cancel_order_reservation_task,
        confirm_order_reservation_task,
    )

    if instance.status == Order.OrderStatus.PAID:
        task = confirm_order_reservation_task
    elif instance.status == Order.OrderStatus.CANCELED:
        task = cancel_order_reservation_task
    else:
        return
    transaction.on_commit(lambda: task.delay(instance.pk))
