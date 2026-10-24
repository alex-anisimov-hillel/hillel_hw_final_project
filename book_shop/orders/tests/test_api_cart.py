import pytest
from decimal import Decimal
from rest_framework.reverse import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_cart_requires_authentication():
    client = APIClient()
    response = client.get(reverse("cart-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_cart_is_empty_for_new_authenticated_user(user):
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("cart-list"))
    assert response.status_code == 200
    assert response.data["items"] == []
    assert Decimal(str(response.data["total_price"])) == Decimal("0")


@pytest.mark.django_db
def test_cart_returns_items_from_session(user, book):
    client = APIClient()
    client.force_authenticate(user=user)
    session = client.session
    session["cart"] = {str(book.id): {"quantity": 2, "price": str(book.price)}}
    session.save()
    response = client.get(reverse("cart-list"))
    assert response.status_code == 200
    assert len(response.data["items"]) == 1
    assert response.data["items"][0]["quantity"] == 2
    assert Decimal(str(response.data["total_price"])) == Decimal(str(book.price)) * 2
