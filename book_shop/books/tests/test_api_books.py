import pytest
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from rest_framework import status


@pytest.mark.django_db
def test_list_books_is_public(book_factory):
    book_factory.create_batch(3)
    client = APIClient()
    response = client.get(reverse("book-list"))
    assert response.status_code == 200
    assert response.data["count"] == 3


@pytest.mark.django_db
def test_retrieve_book_is_public(book):
    client = APIClient()
    response = client.get(reverse("book-detail", args=[book.pk]))
    assert response.status_code == 200
    assert response.data["title"] == book.title


@pytest.mark.django_db
def test_retrieve_nonexistent_book_returns_404():
    client = APIClient()
    response = client.get(reverse("book-detail", args=[999999]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_list_books_api(book_factory):
    book_factory.create_batch(3)
    client = APIClient()
    response = client.get("/api/books/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 3


@pytest.mark.django_db
def test_create_book_api(user_factory, category):
    admin_user = user_factory(is_staff=True)
    client = APIClient()
    client.force_authenticate(user=admin_user)
    payload = {
        "title": "Dune",
        "stock": 5,
        "price": "19.99",
        "category": {"name": category.name, "slug": category.slug},
    }
    response = client.post("/api/books/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_list_books_is_paginated(book_factory):
    book_factory.create_batch(2)
    client = APIClient()
    response = client.get(reverse("book-list"))
    assert set(response.data.keys()) == {"count", "next", "previous", "results"}
    assert len(response.data["results"]) == 2


@pytest.mark.django_db
def test_filter_books_by_price_lt(book_factory):
    cheap = book_factory(price="5.00")
    book_factory(price="50.00")
    client = APIClient()
    response = client.get(reverse("book-list"), {"price_lt": "10.00"})
    assert response.status_code == 200
    titles = [item["title"] for item in response.data["results"]]
    assert titles == [cheap.title]
