import pytest
import responses

from orders.models import Order
from warehouse import order_flow, tasks
from warehouse.exceptions import InsufficientStock, WarehouseUnavailable
from warehouse.tests.conftest import API

RESERVE = f"{API}/reservations/"
RS = Order.ReservationStatus
RID = "6f1c1d3e-0000-4000-8000-000000000001"


def reload(order):
    order.refresh_from_db()
    return order


@pytest.mark.django_db
class TestReserve:
    def test_success_sends_book_ids_and_stores_reservation(
        self, mocked, order_with_items
    ):
        order, (book,) = order_with_items((3,))
        mocked.add(responses.POST, RESERVE, json={"id": RID}, status=201)
        assert order_flow.reserve_order_stock(order.pk) == RS.RESERVED
        order = reload(order)
        assert (str(order.reservation_id), order.reservation_status) == (
            RID,
            RS.RESERVED,
        )
        import json

        body = json.loads(mocked.calls[-1].request.body)
        assert body == {
            "order_id": order.pk,
            "items": [{"book_id": book.pk, "quantity": 3}],
        }

    def test_idempotent_when_already_reserved(self, mocked, order_with_items):
        order, _ = order_with_items()
        mocked.add(responses.POST, RESERVE, json={"id": RID}, status=201)
        order_flow.reserve_order_stock(order.pk)
        calls = len(mocked.calls)
        order_flow.reserve_order_stock(order.pk)
        assert len(mocked.calls) == calls

    def test_insufficient_stock_cancels_order(self, mocked, order_with_items):
        order, _ = order_with_items()
        mocked.add(
            responses.POST,
            RESERVE,
            status=409,
            json={
                "code": "insufficient_stock",
                "shortages": [{"book_id": 1, "requested": 2, "available": 0}],
            },
        )
        with pytest.raises(InsufficientStock):
            order_flow.reserve_order_stock(order.pk)
        order = reload(order)
        assert (order.status, order.reservation_status) == (
            Order.OrderStatus.CANCELED,
            RS.FAILED,
        )

    def test_warehouse_down_parks_order_and_schedules_retry(
        self, mocked, order_with_items, monkeypatch
    ):
        order, _ = order_with_items()
        mocked.add(responses.POST, RESERVE, status=503)
        scheduled = []
        monkeypatch.setattr(order_flow, "_schedule_retry", scheduled.append)
        assert order_flow.reserve_order_stock(order.pk) == RS.PENDING_RETRY
        assert reload(order).reservation_status == RS.PENDING_RETRY
        assert scheduled == [order.pk]

    def test_task_variant_raises_for_celery_retry(self, mocked, order_with_items):
        order, _ = order_with_items()
        mocked.add(responses.POST, RESERVE, status=503)
        with pytest.raises(WarehouseUnavailable):
            order_flow.reserve_order_stock(order.pk, retry_via_celery=False)

    def test_disabled_flag_makes_no_calls(self, mocked, order_with_items, settings):
        settings.WAREHOUSE_ENABLED = False
        order, _ = order_with_items()
        assert order_flow.reserve_order_stock(order.pk) == RS.NONE
        assert len(mocked.calls) == 0

    def test_retry_task_recovers_after_outage(self, mocked, order_with_items):
        order, _ = order_with_items()
        Order.objects.filter(pk=order.pk).update(reservation_status=RS.PENDING_RETRY)
        mocked.add(responses.POST, RESERVE, json={"id": RID}, status=201)
        assert tasks.reserve_order_stock_task(order.pk) == RS.RESERVED

    def test_retry_task_emails_customer_when_stock_gone(
        self, mocked, order_with_items, mailoutbox
    ):
        order, _ = order_with_items(email="buyer@example.com")
        mocked.add(
            responses.POST,
            RESERVE,
            status=409,
            json={"code": "insufficient_stock", "shortages": []},
        )
        assert tasks.reserve_order_stock_task(order.pk) == "failed"
        assert len(mailoutbox) == 1 and mailoutbox[0].to == ["buyer@example.com"]


@pytest.mark.django_db
class TestConfirmAndCancel:
    def reserved_order(self, order_with_items):
        order, _ = order_with_items()
        Order.objects.filter(pk=order.pk).update(
            reservation_id=RID, reservation_status=RS.RESERVED
        )
        return reload(order)

    def test_paid_order_confirms_reservation(
        self, mocked, order_with_items, django_capture_on_commit_callbacks
    ):
        order = self.reserved_order(order_with_items)
        mocked.add(
            responses.POST,
            f"{API}/reservations/{RID}/confirm/",
            json={"status": "confirmed"},
        )
        with django_capture_on_commit_callbacks(execute=True):
            order.status = Order.OrderStatus.PAID
            order.save()
        assert reload(order).reservation_status == RS.CONFIRMED

    def test_cancelled_order_releases_reservation(
        self, mocked, order_with_items, django_capture_on_commit_callbacks
    ):
        order = self.reserved_order(order_with_items)
        mocked.add(
            responses.POST,
            f"{API}/reservations/{RID}/cancel/",
            json={"status": "cancelled"},
        )
        with django_capture_on_commit_callbacks(execute=True):
            order.status = Order.OrderStatus.CANCELED
            order.save()
        assert reload(order).reservation_status == RS.RELEASED

    def test_unrelated_status_changes_do_nothing(
        self, mocked, order_with_items, django_capture_on_commit_callbacks
    ):
        order = self.reserved_order(order_with_items)
        with django_capture_on_commit_callbacks(execute=True):
            order.status = Order.OrderStatus.SENT
            order.save()
        assert len(mocked.calls) == 0

    def test_repeated_saves_do_not_call_warehouse_again(
        self, mocked, order_with_items, django_capture_on_commit_callbacks
    ):
        order = self.reserved_order(order_with_items)
        mocked.add(responses.POST, f"{API}/reservations/{RID}/confirm/", json={})
        order.status = Order.OrderStatus.PAID
        with django_capture_on_commit_callbacks(execute=True):
            order.save()
        calls = len(mocked.calls)
        with django_capture_on_commit_callbacks(execute=True):
            reload(order).save()
        assert len(mocked.calls) == calls

    def test_confirm_after_expiry_marks_failed_and_logs_error(
        self, mocked, order_with_items, caplog
    ):
        order = self.reserved_order(order_with_items)
        mocked.add(
            responses.POST,
            f"{API}/reservations/{RID}/confirm/",
            status=409,
            json={"code": "invalid_reservation_state"},
        )
        assert order_flow.confirm_order_reservation(order.pk) == RS.FAILED
        assert "needs manual handling" in caplog.text

    def test_paid_while_warehouse_was_down_reserves_then_confirms(
        self, mocked, order_with_items
    ):
        order, _ = order_with_items()
        Order.objects.filter(pk=order.pk).update(reservation_status=RS.PENDING_RETRY)
        mocked.add(responses.POST, RESERVE, json={"id": RID}, status=201)
        mocked.add(responses.POST, f"{API}/reservations/{RID}/confirm/", json={})
        assert order_flow.confirm_order_reservation(order.pk) == RS.CONFIRMED

    def test_cancel_without_known_reservation_looks_it_up(
        self, mocked, order_with_items
    ):
        order, _ = order_with_items()
        Order.objects.filter(pk=order.pk).update(reservation_status=RS.PENDING_RETRY)
        mocked.add(responses.GET, RESERVE, json={"results": [{"id": RID}]})
        mocked.add(responses.POST, f"{API}/reservations/{RID}/cancel/", json={})
        assert order_flow.cancel_order_reservation(order.pk) == RS.RELEASED

    def test_cancel_when_nothing_was_reserved(self, mocked, order_with_items):
        order, _ = order_with_items()
        Order.objects.filter(pk=order.pk).update(reservation_status=RS.PENDING_RETRY)
        mocked.add(responses.GET, RESERVE, json={"results": []})
        assert order_flow.cancel_order_reservation(order.pk) == RS.RELEASED

    def test_periodic_retry_requeues_pending_orders(self, mocked, order_with_items):
        order, _ = order_with_items()
        Order.objects.filter(pk=order.pk).update(reservation_status=RS.PENDING_RETRY)
        mocked.add(responses.POST, RESERVE, json={"id": RID}, status=201)
        assert tasks.retry_pending_reservations() == {"requeued": 1}
        assert reload(order).reservation_status == RS.RESERVED
