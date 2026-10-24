import pytest


@pytest.mark.django_db
def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_book_list(client):
    response = client.get("/books/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_specific_book(client, book_factory):
    book = book_factory()
    response = client.get(f"/books/{book.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_specific_book_create(client, book):
    response = client.get(f"/books/admin/create/{book.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_specific_book_edit(client, book):
    response = client.get(f"/books/admin/edit/{book.pk}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_specific_book_delete(client, book):
    response = client.get(f"/books/admin/delete/{book.pk}/")
    assert response.status_code == 200
