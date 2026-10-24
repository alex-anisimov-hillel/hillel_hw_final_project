import pytest
from rest_framework.reverse import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_payment_list_requires_authentication():
    client = APIClient()
    response = client.get(reverse("payment-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_payment_list_only_returns_own_payments(user_factory, payment_factory):
    owner = user_factory(is_staff=False)
    other = user_factory(is_staff=False)
    payment_factory(user=owner)
    payment_factory(user=other)
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.get(reverse("payment-list"))
    assert response.status_code == 200
    assert len(response.data) == 1


@pytest.mark.django_db
def test_payment_retrieve_own_payment_succeeds(user_factory, payment_factory):
    owner = user_factory(is_staff=False)
    payment = payment_factory(user=owner)
    payment.refresh_from_db()
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.get(reverse("payment-detail", args=[payment.pk]))
    assert response.status_code == 200
    assert response.data["id"] == str(payment.pk)


@pytest.mark.django_db
def test_payment_retrieve_other_users_payment_returns_404(
    user_factory, payment_factory
):
    owner = user_factory(is_staff=False)
    other = user_factory(is_staff=False)
    payment = payment_factory(user=other)
    payment.refresh_from_db()
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.get(reverse("payment-detail", args=[payment.pk]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_create_payment_intent_requires_authentication():
    client = APIClient()
    response = client.post(
        reverse("payment-create-payment-intent"), {"amount": "15.00"}
    )
    assert response.status_code == 401
