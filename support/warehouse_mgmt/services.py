"""Stock business logic. Views and tasks stay thin and call these functions.

Concurrency rules
-----------------
* Every mutation runs in ``transaction.atomic`` and takes row locks with
  ``select_for_update`` in a fixed order (reservation first, then stock items ordered
  by pk) so concurrent orders cannot oversell or deadlock.
* ``reserve_stock`` is idempotent per ``order_id`` (unique column), so ProjectA can
  safely retry it after a timeout.
* ``confirm``/``cancel``/``expire`` are idempotent as well.
* Caches and webhooks fire from ``transaction.on_commit`` - never for rolled-back work.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound

from warehouse_mgmt.exceptions import (
    InsufficientStock,
    InvalidAdjustment,
    ReservationStateError,
    UnknownWarehouse,
)
from warehouse_mgmt.models import (
    ReservationLine,
    StockItem,
    StockMovement,
    StockReservation,
    Warehouse,
)

logger = logging.getLogger(__name__)

Status = StockReservation.Status
Kind = StockMovement.Kind


# ---------------------------------------------------------------------------
# Cache + notifications
# ---------------------------------------------------------------------------
def cache_key(book_id: int) -> str:
    return f"stock:{book_id}"


def _after_commit(book_ids):
    """Drop cached availability and notify ProjectA once the transaction commits."""
    ids = sorted(set(book_ids))

    def _run():
        cache.delete_many([cache_key(b) for b in ids])
        from warehouse_mgmt.tasks import notify_stock_changed

        try:
            notify_stock_changed.delay(ids)
        except Exception:  # broker down must not break a committed stock change
            logger.exception("Could not enqueue stock-changed webhook for %s", ids)

    transaction.on_commit(_run)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def get_availability(book_ids, use_cache=True) -> dict:
    """Aggregate availability across active warehouses, ``{book_id: {...}}``."""
    ids = list(dict.fromkeys(int(b) for b in book_ids))
    result = {}
    if use_cache and ids:
        cached = cache.get_many([cache_key(b) for b in ids])
        for b in ids:
            hit = cached.get(cache_key(b))
            if hit is not None:
                result[b] = hit
    missing = [b for b in ids if b not in result]
    if missing:
        rows = (
            StockItem.objects.filter(book_id__in=missing, warehouse__is_active=True)
            .values("book_id")
            .annotate(q=Sum("quantity"), r=Sum("reserved"))
            .order_by()
        )
        found = {row["book_id"]: row for row in rows}
        fresh = {}
        for b in missing:
            row = found.get(b)
            quantity = row["q"] if row else 0
            reserved = row["r"] if row else 0
            fresh[b] = {
                "book_id": b,
                "tracked": row is not None,
                "quantity": quantity,
                "reserved": reserved,
                "available": quantity - reserved,
                "in_stock": quantity - reserved > 0,
            }
        cache.set_many(
            {cache_key(b): v for b, v in fresh.items()}, settings.STOCK_CACHE_TTL
        )
        result.update(fresh)
    return {b: result[b] for b in ids}


def low_stock_items():
    return (
        StockItem.objects.filter(warehouse__is_active=True)
        .annotate(avail=F("quantity") - F("reserved"))
        .filter(avail__lte=F("low_stock_threshold"))
        .select_related("warehouse")
        .order_by("avail", "book_id")
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _locked_items(book_ids):
    return list(
        StockItem.objects.select_for_update(of=("self",))
        .select_related("warehouse")
        .filter(book_id__in=book_ids, warehouse__is_active=True)
        .order_by("pk")
    )


def _lock_reservation(reservation_id) -> StockReservation:
    try:
        return StockReservation.objects.select_for_update().get(pk=reservation_id)
    except StockReservation.DoesNotExist as exc:
        raise NotFound() from exc


def _lock_lines(reservation):
    lines = list(reservation.lines.all())
    pks = sorted({line.stock_item_id for line in lines})
    items = {
        i.pk: i
        for i in StockItem.objects.select_for_update().filter(pk__in=pks).order_by("pk")
    }
    return lines, items


def _get_warehouse(code) -> Warehouse:
    warehouse = Warehouse.objects.filter(
        code=code or settings.DEFAULT_WAREHOUSE_CODE, is_active=True
    ).first()
    if warehouse is None:
        raise UnknownWarehouse()
    return warehouse


def _get_or_create_locked_item(warehouse, book_id) -> StockItem:
    qs = StockItem.objects.select_for_update().filter(
        warehouse=warehouse, book_id=book_id
    )
    item = qs.first()
    if item is None:
        try:
            with transaction.atomic():
                StockItem.objects.create(warehouse=warehouse, book_id=book_id)
        except IntegrityError:  # lost a race with a concurrent creator - just re-read
            pass
        item = qs.get()
    return item


# ---------------------------------------------------------------------------
# Reservations
# ---------------------------------------------------------------------------
def reserve_stock(*, order_id, items, user=None, ttl_minutes=None):
    """Reserve ``items`` (iterable of ``(book_id, quantity)``) for ProjectA's order.

    Returns ``(reservation, created)``. ``created`` is False when a reservation for
    this order already exists (idempotent retry). Raises ``InsufficientStock`` (and
    changes nothing) if any book cannot be fully covered.
    """
    existing = StockReservation.objects.filter(order_id=order_id).first()
    if existing:
        return existing, False

    wanted = defaultdict(int)
    for book_id, quantity in items:
        wanted[int(book_id)] += int(quantity)

    expires_at = timezone.now() + timedelta(
        minutes=ttl_minutes or settings.RESERVATION_TTL_MINUTES
    )
    try:
        with transaction.atomic():
            # Insert first: a concurrent request for the same order blocks here and then
            # fails with IntegrityError, which we turn into the idempotent answer.
            reservation = StockReservation.objects.create(
                order_id=order_id, expires_at=expires_at, created_by=user
            )
            by_book = defaultdict(list)
            for item in _locked_items(wanted):
                by_book[item.book_id].append(item)

            plan, shortages = [], []
            for book_id, requested in wanted.items():
                remaining = requested
                candidates = sorted(
                    by_book.get(book_id, []),
                    key=lambda i: (i.warehouse.priority, -i.available, i.pk),
                )
                for item in candidates:
                    take = min(item.available, remaining)
                    if take > 0:
                        plan.append((item, take))
                        remaining -= take
                    if remaining == 0:
                        break
                if remaining:
                    shortages.append(
                        {
                            "book_id": book_id,
                            "requested": requested,
                            "available": requested - remaining,
                        }
                    )
            if shortages:
                raise InsufficientStock(shortages)  # rolls back the reservation row too

            for item, take in plan:
                item.reserved += take
                item.save(update_fields=["reserved", "updated_at"])
                ReservationLine.objects.create(
                    reservation=reservation,
                    stock_item=item,
                    book_id=item.book_id,
                    quantity=take,
                )
                StockMovement.objects.create(
                    stock_item=item,
                    kind=Kind.RESERVE,
                    reserved_delta=take,
                    reservation=reservation,
                    created_by=user,
                    note=f"order #{order_id}",
                )
    except IntegrityError:
        existing = StockReservation.objects.filter(order_id=order_id).first()
        if existing is None:
            raise
        return existing, False

    _after_commit(wanted.keys())
    logger.info(
        "Reserved stock for order %s (reservation %s)", order_id, reservation.pk
    )
    return reservation, True


def confirm_reservation(reservation_id, user=None) -> StockReservation:
    """Order paid/shipped: turn reserved units into a real decrease of on-hand stock.

    A pending reservation can be confirmed even slightly after ``expires_at`` as long
    as the expiry task has not released it yet - we never want 'paid but expired'.
    """
    with transaction.atomic():
        reservation = _lock_reservation(reservation_id)
        if reservation.status == Status.CONFIRMED:
            return reservation
        if reservation.status != Status.PENDING:
            raise ReservationStateError()
        lines, items = _lock_lines(reservation)
        for line in lines:
            item = items[line.stock_item_id]
            item.quantity -= line.quantity
            item.reserved -= line.quantity
            item.save(update_fields=["quantity", "reserved", "updated_at"])
            StockMovement.objects.create(
                stock_item=item,
                kind=Kind.SHIP,
                quantity_delta=-line.quantity,
                reserved_delta=-line.quantity,
                reservation=reservation,
                created_by=user,
                note=f"order #{reservation.order_id}",
            )
        reservation.status = Status.CONFIRMED
        reservation.save(update_fields=["status", "updated_at"])
    _after_commit(line.book_id for line in lines)
    logger.info(
        "Confirmed reservation %s (order %s)", reservation.pk, reservation.order_id
    )
    return reservation


def _release(reservation, new_status, note, user=None):
    lines, items = _lock_lines(reservation)
    for line in lines:
        item = items[line.stock_item_id]
        item.reserved -= line.quantity
        item.save(update_fields=["reserved", "updated_at"])
        StockMovement.objects.create(
            stock_item=item,
            kind=Kind.RELEASE,
            reserved_delta=-line.quantity,
            reservation=reservation,
            created_by=user,
            note=note,
        )
    reservation.status = new_status
    reservation.save(update_fields=["status", "updated_at"])
    _after_commit(line.book_id for line in lines)


def cancel_reservation(reservation_id, user=None) -> StockReservation:
    with transaction.atomic():
        reservation = _lock_reservation(reservation_id)
        if reservation.status in (Status.CANCELLED, Status.EXPIRED):
            return reservation
        if reservation.status != Status.PENDING:
            raise ReservationStateError()  # already shipped - needs a return flow
        _release(
            reservation,
            Status.CANCELLED,
            f"cancelled order #{reservation.order_id}",
            user,
        )
    logger.info(
        "Cancelled reservation %s (order %s)", reservation.pk, reservation.order_id
    )
    return reservation


def expire_reservation(reservation_id) -> StockReservation:
    with transaction.atomic():
        reservation = _lock_reservation(reservation_id)
        if (
            reservation.status != Status.PENDING
            or reservation.expires_at > timezone.now()
        ):
            return reservation
        _release(reservation, Status.EXPIRED, f"expired order #{reservation.order_id}")
    logger.info(
        "Expired reservation %s (order %s)", reservation.pk, reservation.order_id
    )
    return reservation


# ---------------------------------------------------------------------------
# Restock / adjust
# ---------------------------------------------------------------------------
def restock(
    *, book_id, quantity, warehouse_code=None, title="", isbn="", note="", user=None
):
    with transaction.atomic():
        warehouse = _get_warehouse(warehouse_code)
        item = _get_or_create_locked_item(warehouse, book_id)
        item.quantity += quantity
        if title and not item.title:
            item.title = title
        if isbn and not item.isbn:
            item.isbn = isbn
        item.save(update_fields=["quantity", "title", "isbn", "updated_at"])
        StockMovement.objects.create(
            stock_item=item,
            kind=Kind.RESTOCK,
            quantity_delta=quantity,
            note=note,
            created_by=user,
        )
        _after_commit([book_id])
    logger.info("Restocked book %s +%s in %s", book_id, quantity, warehouse.code)
    return item


def adjust_stock(*, book_id, delta, note, warehouse_code=None, user=None):
    """Correct on-hand quantity (damage, stocktaking). Never below reserved."""
    with transaction.atomic():
        warehouse = _get_warehouse(warehouse_code)
        item = (
            StockItem.objects.select_for_update()
            .filter(warehouse=warehouse, book_id=book_id)
            .first()
        )
        if item is None:
            raise NotFound()
        new_quantity = item.quantity + delta
        if new_quantity < item.reserved:
            raise InvalidAdjustment()
        item.quantity = new_quantity
        item.save(update_fields=["quantity", "updated_at"])
        StockMovement.objects.create(
            stock_item=item,
            kind=Kind.ADJUST,
            quantity_delta=delta,
            note=note,
            created_by=user,
        )
        _after_commit([book_id])
    logger.info(
        "Adjusted book %s by %s in %s: %s", book_id, delta, warehouse.code, note
    )
    return item
