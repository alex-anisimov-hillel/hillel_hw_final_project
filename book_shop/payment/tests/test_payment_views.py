import asyncio
from unittest.mock import patch

import pytest

from payment import views as payment_views


@pytest.mark.django_db
def test_cart(client):
    response = client.get("/payment/cart/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_cart_add(client, book):
    response = client.get(f"/payment/cart/add/{book.pk}/", follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_cart_remove(client, book):
    response = client.get(f"/payment/cart/remove/{book.pk}/", follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_order_create(client, book):
    session = client.session
    session["cart"] = {str(book.id): {"quantity": 1, "price": str(book.price)}}
    session.save()
    response = client.get("/payment/order_create/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_cart_checkout(client, order):
    response = client.get(f"/payment/checkout/{order.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
@patch("payment.views.send_order_confirmation_email")
def test_email_send(mock_email_send, order):
    asyncio.run(payment_views.send_order_confirmation_email(order.user.email, order.id))
    mock_email_send.assert_called_once()
