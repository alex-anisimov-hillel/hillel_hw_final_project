import pytest
from rest_framework.reverse import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_list_categories_is_public(category_factory):
    category_factory.create_batch(3)
    client = APIClient()
    response = client.get(reverse("category-list"))
    assert response.status_code == 200
    assert len(response.data) == 3


@pytest.mark.django_db
def test_list_categories_returns_expected_fields(category):
    client = APIClient()
    response = client.get(reverse("category-list"))
    item = response.data[0]
    assert {"id", "name", "slug"} <= set(item.keys())
    assert item["name"] == category.name


@pytest.mark.django_db
def test_retrieve_category_is_public(category):
    client = APIClient()
    response = client.get(reverse("category-detail", args=[category.pk]))
    assert response.status_code == 200
    assert response.data["name"] == category.name


@pytest.mark.django_db
def test_create_category_requires_authentication():
    client = APIClient()
    response = client.post(
        reverse("category-list"), {"name": "Sci-Fi", "slug": "sci-fi"}
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_delete_category_forbidden_for_non_staff(user_factory, category):
    client = APIClient()
    user = user_factory(is_staff=False)
    client.force_authenticate(user=user)
    response = client.delete(reverse("category-detail", args=[category.pk]))
    assert response.status_code == 403
