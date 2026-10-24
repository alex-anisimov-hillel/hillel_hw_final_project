import base64
import json
import time

import pytest
import responses as responses_lib

API = "http://warehouse.test/api"
SECRET = "shared-webhook-secret-for-tests"


def make_jwt(ttl=900):
    body = (
        base64.urlsafe_b64encode(json.dumps({"exp": time.time() + ttl}).encode())
        .decode()
        .rstrip("=")
    )
    return f"header.{body}.signature"


@pytest.fixture(autouse=True)
def warehouse_settings(settings):
    settings.WAREHOUSE_ENABLED = True
    settings.WAREHOUSE_API_URL = API
    settings.WAREHOUSE_SERVICE_EMAIL = "projecta@example.com"
    settings.WAREHOUSE_SERVICE_PASSWORD = "pw"
    settings.WAREHOUSE_WEBHOOK_SECRET = SECRET
    settings.WAREHOUSE_MAX_ATTEMPTS = 2
    settings.CELERY_TASK_ALWAYS_EAGER = True


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("warehouse.client.time.sleep", lambda s: None)


@pytest.fixture
def mocked():
    """`responses` mock with a working login endpoint pre-registered."""
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses_lib.POST,
            f"{API}/auth/token/",
            json={"access": make_jwt(), "refresh": make_jwt(86400)},
        )
        yield rsps


@pytest.fixture
def order_with_items(book_factory, order_factory):
    from orders.models import Order, OrderItem

    def make(quantities=(2,), **kwargs):
        books = [book_factory(stock=50) for _ in quantities]
        order = order_factory(
            status=Order.OrderStatus.CREATED, payment_method=None, **kwargs
        )
        for book, qty in zip(books, quantities):
            OrderItem.objects.create(
                order=order, book=book, price=book.price, quantity=qty
            )
        return order, books

    return make
