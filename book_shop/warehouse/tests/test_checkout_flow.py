"""End-to-end through the real views: cart -> checkout -> reservation -> payment."""

import pytest
import responses
from rest_framework.reverse import reverse
from django.utils import translation

from orders.models import Order
from warehouse.tests.conftest import API

RESERVE = f"{API}/reservations/"
RID = "6f1c1d3e-0000-4000-8000-000000000002"
FORM = {
    "email": "buyer@example.com",
    "phone_number": "123",
    "address": "Street 1",
    "city": "Dnipro",
}


def fill_cart(client, book, quantity=2):
    client.post(f"/payment/cart/add/{book.pk}/", {"quantity": quantity})


@pytest.mark.django_db
class TestCheckout:
    def test_success_reserves_stock_and_clears_cart(self, client, mocked, book):
        fill_cart(client, book)
        mocked.add(responses.POST, RESERVE, json={"id": RID}, status=201)
        resp = client.post("/payment/order_create/", FORM)
        order = Order.objects.get()
        assert resp.status_code == 200
        assert order.reservation_status == Order.ReservationStatus.RESERVED
        assert not client.session.get("cart")

    def test_insufficient_stock_keeps_cart_and_explains(self, client, mocked, book):
        fill_cart(client, book, 5)
        mocked.add(
            responses.POST,
            RESERVE,
            status=409,
            json={
                "code": "insufficient_stock",
                "shortages": [{"book_id": book.pk, "requested": 5, "available": 1}],
            },
        )
        resp = client.post("/payment/order_create/", FORM)
        assert resp.status_code == 409
        text = resp.content.decode()
        assert "Not enough stock for" in text and book.title in text
        assert client.session.get("cart")  # customer can adjust and retry
        assert Order.objects.get().status == Order.OrderStatus.CANCELED

    def test_message_is_translated(self, client, mocked, book):
        fill_cart(client, book, 5)
        mocked.add(
            responses.POST,
            RESERVE,
            status=409,
            json={
                "code": "insufficient_stock",
                "shortages": [{"book_id": book.pk, "requested": 5, "available": 1}],
            },
        )
        with translation.override("uk"):
            resp = client.post(
                "/payment/order_create/", FORM, HTTP_ACCEPT_LANGUAGE="uk"
            )
        assert "Недостатньо книг на складі" in resp.content.decode()

    def test_warehouse_outage_still_accepts_the_order(
        self, client, mocked, book, monkeypatch
    ):
        from warehouse import order_flow

        scheduled = []
        monkeypatch.setattr(order_flow, "_schedule_retry", scheduled.append)
        fill_cart(client, book)
        mocked.add(responses.POST, RESERVE, status=503)
        resp = client.post("/payment/order_create/", FORM)
        order = Order.objects.get()
        assert resp.status_code == 200  # graceful degradation: success page
        assert order.reservation_status == Order.ReservationStatus.PENDING_RETRY
        assert scheduled == [order.pk]
        assert not client.session.get("cart")

    def test_disabled_integration_behaves_like_before(
        self, client, mocked, book, settings
    ):
        settings.WAREHOUSE_ENABLED = False
        fill_cart(client, book)
        assert client.post("/payment/order_create/", FORM).status_code == 200
        assert len(mocked.calls) == 0
        assert Order.objects.get().reservation_status == Order.ReservationStatus.NONE


@pytest.mark.django_db
def test_confirm_payment_marks_order_paid_and_confirms_reservation(
    mocked,
    user_factory,
    payment_factory,
    order_with_items,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    from rest_framework.test import APIClient
    from payment.models import Payment
    from payment.stripe_service import StripePayment

    user = user_factory(is_staff=False)
    payment = payment_factory(user=user, status=Payment.Status.PENDING)
    payment.refresh_from_db()  # factory's int id is normalised to a UUID
    order, _ = order_with_items()
    Order.objects.filter(pk=order.pk).update(
        reservation_id=RID, reservation_status="reserved"
    )

    def fake_confirm(payment_id, stripe_payment_intent_id):
        payment.status = Payment.Status.SUCCESS
        payment.save()
        return payment

    monkeypatch.setattr(StripePayment, "confirm_payment", staticmethod(fake_confirm))
    mocked.add(responses.POST, f"{API}/reservations/{RID}/confirm/", json={})
    client = APIClient()
    client.force_authenticate(user)
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            reverse("payment-confirm-payment", args=[payment.pk]),
            {"order_id": order.pk},
            format="json",
        )
    order.refresh_from_db()
    assert resp.status_code == 200, resp.content
    assert order.status == Order.OrderStatus.PAID
    assert order.reservation_status == Order.ReservationStatus.CONFIRMED
