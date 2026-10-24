import pytest


@pytest.mark.django_db
def test_category_to_string(category):
    assert str(category) == f"{category.name}"


@pytest.mark.django_db
def test_category_creation(category_factory):
    category = category_factory(name="Fantasy")
    assert category.name == "Fantasy"


@pytest.mark.django_db
def test_multiple_books(category_factory):
    category1 = category_factory()
    category2 = category_factory()
    assert category1 != category2
