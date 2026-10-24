import pytest
from django.utils import timezone

from warehouse_mgmt import services
from warehouse_mgmt.exceptions import (
    InsufficientStock,
    InvalidAdjustment,
    ReservationStateError,
    UnknownWarehouse,
)
from warehouse_mgmt.models import StockMovement, StockReservation


@pytest.mark.django_db
class TestReserve:
    def test_reserve_holds_stock_and_logs_movement(self, stock):
        item = stock(1, 10)
        reservation, created = services.reserve_stock(order_id=7, items=[(1, 4)])
        item.refresh_from_db()
        assert created and reservation.status == "pending"
        assert (item.quantity, item.reserved, item.available) == (10, 4, 6)
        movement = StockMovement.objects.get(reservation=reservation)
        assert (movement.kind, movement.reserved_delta) == ("reserve", 4)

    def test_idempotent_per_order(self, stock):
        item = stock(1, 10)
        first, c1 = services.reserve_stock(order_id=7, items=[(1, 4)])
        again, c2 = services.reserve_stock(order_id=7, items=[(1, 4)])
        item.refresh_from_db()
        assert (c1, c2) == (True, False) and first.pk == again.pk
        assert item.reserved == 4  # not reserved twice

    def test_duplicate_book_lines_are_merged(self, stock):
        item = stock(1, 10)
        services.reserve_stock(order_id=1, items=[(1, 2), (1, 3)])
        item.refresh_from_db()
        assert item.reserved == 5

    def test_insufficient_stock_is_atomic(self, stock):
        a, b = stock(1, 10), stock(2, 1)
        with pytest.raises(InsufficientStock) as exc:
            services.reserve_stock(order_id=9, items=[(1, 5), (2, 3)])
        assert exc.value.shortages == [{"book_id": 2, "requested": 3, "available": 1}]
        a.refresh_from_db(), b.refresh_from_db()
        assert (a.reserved, b.reserved) == (0, 0)  # nothing partially reserved
        assert not StockReservation.objects.filter(order_id=9).exists()

    def test_unknown_book_is_a_shortage(self, db, main_wh):
        with pytest.raises(InsufficientStock) as exc:
            services.reserve_stock(order_id=1, items=[(999, 1)])
        assert exc.value.shortages[0]["available"] == 0

    def test_allocates_across_warehouses_by_priority(self, stock, main_wh, second_wh):
        near = stock(1, 3, warehouse=main_wh)  # priority 10
        far = stock(1, 10, warehouse=second_wh)  # priority 50
        reservation, _ = services.reserve_stock(order_id=1, items=[(1, 5)])
        near.refresh_from_db(), far.refresh_from_db()
        assert (near.reserved, far.reserved) == (3, 2)
        assert reservation.lines.count() == 2

    def test_inactive_warehouse_is_ignored(self, stock, second_wh):
        second_wh.is_active = False
        second_wh.save()
        stock(1, 10, warehouse=second_wh)
        with pytest.raises(InsufficientStock):
            services.reserve_stock(order_id=1, items=[(1, 1)])


@pytest.mark.django_db
class TestLifecycle:
    def test_confirm_decreases_on_hand(self, stock):
        item = stock(1, 10)
        res, _ = services.reserve_stock(order_id=1, items=[(1, 4)])
        services.confirm_reservation(res.pk)
        item.refresh_from_db()
        assert (item.quantity, item.reserved) == (6, 0)
        assert StockReservation.objects.get(pk=res.pk).status == "confirmed"

    def test_confirm_is_idempotent(self, stock):
        item = stock(1, 10)
        res, _ = services.reserve_stock(order_id=1, items=[(1, 4)])
        services.confirm_reservation(res.pk)
        services.confirm_reservation(res.pk)
        item.refresh_from_db()
        assert item.quantity == 6

    def test_cancel_releases_and_is_idempotent(self, stock):
        item = stock(1, 10)
        res, _ = services.reserve_stock(order_id=1, items=[(1, 4)])
        services.cancel_reservation(res.pk)
        services.cancel_reservation(res.pk)
        item.refresh_from_db()
        assert (item.quantity, item.reserved) == (10, 0)

    def test_cannot_cancel_confirmed(self, stock):
        stock(1, 10)
        res, _ = services.reserve_stock(order_id=1, items=[(1, 4)])
        services.confirm_reservation(res.pk)
        with pytest.raises(ReservationStateError):
            services.cancel_reservation(res.pk)

    def test_cannot_confirm_cancelled(self, stock):
        stock(1, 10)
        res, _ = services.reserve_stock(order_id=1, items=[(1, 4)])
        services.cancel_reservation(res.pk)
        with pytest.raises(ReservationStateError):
            services.confirm_reservation(res.pk)

    def test_expire_only_after_deadline(self, stock):
        item = stock(1, 10)
        res, _ = services.reserve_stock(order_id=1, items=[(1, 4)])
        services.expire_reservation(res.pk)  # not due yet
        item.refresh_from_db()
        assert item.reserved == 4
        StockReservation.objects.filter(pk=res.pk).update(
            expires_at=timezone.now() - timezone.timedelta(minutes=1)
        )
        services.expire_reservation(res.pk)
        item.refresh_from_db()
        assert item.reserved == 0
        assert StockReservation.objects.get(pk=res.pk).status == "expired"

    def test_stock_freed_by_cancel_can_be_reserved_again(self, stock):
        stock(1, 5)
        res, _ = services.reserve_stock(order_id=1, items=[(1, 5)])
        with pytest.raises(InsufficientStock):
            services.reserve_stock(order_id=2, items=[(1, 1)])
        services.cancel_reservation(res.pk)
        services.reserve_stock(order_id=2, items=[(1, 1)])


@pytest.mark.django_db
class TestRestockAdjust:
    def test_restock_creates_item_and_ledger(self, main_wh):
        item = services.restock(book_id=5, quantity=20, title="Dune", isbn="978")
        assert (item.quantity, item.title, item.warehouse) == (20, "Dune", main_wh)
        services.restock(book_id=5, quantity=5)
        item.refresh_from_db()
        assert item.quantity == 25
        assert (
            StockMovement.objects.filter(stock_item=item, kind="restock").count() == 2
        )

    def test_restock_unknown_warehouse(self, db):
        with pytest.raises(UnknownWarehouse):
            services.restock(book_id=1, quantity=1, warehouse_code="nope")

    def test_adjust_cannot_go_below_reserved(self, stock):
        stock(1, 10)
        services.reserve_stock(order_id=1, items=[(1, 8)])
        with pytest.raises(InvalidAdjustment):
            services.adjust_stock(book_id=1, delta=-5, note="damaged")
        item = services.adjust_stock(book_id=1, delta=-2, note="damaged")
        assert item.quantity == 8


@pytest.mark.django_db
class TestAvailability:
    def test_aggregates_and_caches(self, stock, second_wh, django_assert_num_queries):
        stock(1, 10)
        stock(1, 5, warehouse=second_wh)
        first = services.get_availability([1, 2])
        assert first[1] == {
            "book_id": 1,
            "tracked": True,
            "quantity": 15,
            "reserved": 0,
            "available": 15,
            "in_stock": True,
        }
        assert first[2]["tracked"] is False and first[2]["in_stock"] is False
        with django_assert_num_queries(0):
            assert services.get_availability([1, 2]) == first

    def test_cache_invalidated_on_commit(
        self, stock, django_capture_on_commit_callbacks
    ):
        stock(1, 10)
        services.get_availability([1])
        with django_capture_on_commit_callbacks(execute=True):
            services.reserve_stock(order_id=1, items=[(1, 4)])
        assert services.get_availability([1])[1]["available"] == 6

    def test_low_stock_items(self, stock):
        stock(1, 5, low_stock_threshold=10)
        stock(2, 50, low_stock_threshold=10)
        assert [i.book_id for i in services.low_stock_items()] == [1]
