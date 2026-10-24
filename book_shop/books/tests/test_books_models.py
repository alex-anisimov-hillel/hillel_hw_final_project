import pytest


@pytest.mark.django_db
def test_book_str_representation(book):
    assert str(book) == f"{book.title} ({book.author})"


@pytest.mark.django_db
def test_book_default_stock_is_valid(book_factory):
    book = book_factory(stock=10)
    assert book.stock == 10


@pytest.mark.django_db
def test_multiple_books(book_factory):
    book1 = book_factory()
    book2 = book_factory()
    assert book1.category_id != book2.category_id


@pytest.mark.django_db
def test_book_belongs_to_given_category(book_factory, category_factory):
    fiction = category_factory(name="Fantasy", slug="fantasy")
    book = book_factory(category=fiction)
    assert book.category.name == "Fantasy"
