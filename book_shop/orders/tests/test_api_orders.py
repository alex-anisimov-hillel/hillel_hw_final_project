import pytest
from rest_framework.reverse import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_order_list_requires_authentication():
    client = APIClient()
    response = client.get(reverse("order-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_order_list_forbidden_for_non_admin_user(user_factory):
    user = user_factory(is_staff=False)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("order-list"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_order_list_allowed_for_admin_user(user_factory, order_factory):
    admin = user_factory(is_staff=True)
    order_factory.create_batch(2)
    client = APIClient()
    client.force_authenticate(user=admin)
    response = client.get(reverse("order-list"))
    assert response.status_code == 200
    assert len(response.data) == 2


@pytest.mark.django_db
def test_order_create_forbidden_for_non_admin_user(user_factory):
    user = user_factory(is_staff=False)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(reverse("order-list"), {"total_price": "25.00"})
    assert response.status_code == 403


@pytest.mark.django_db
def test_order_create_allowed_for_admin_user(user_factory):
    admin = user_factory(is_staff=True)
    client = APIClient()
    client.force_authenticate(user=admin)
    response = client.post(reverse("order-list"), {"total_price": "25.00"})
    assert response.status_code == 201
    assert response.data["total_price"] == "25.00"
    assert response.data["status"] == "created"
