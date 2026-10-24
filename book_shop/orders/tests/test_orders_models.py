import pytest
from decimal import Decimal

from orders.models import Order, OrderItem


@pytest.mark.django_db
def test_order_for_valid(order_factory):
    order = order_factory(city="Some city")
    assert order.city == "Some city"


@pytest.mark.django_db
def test_different_orders(order_factory):
    order1 = order_factory(city="Some city")
    order2 = order_factory(city="Another city")
    assert order1 != order2


@pytest.mark.django_db
def test_different_orders_same_user(order_factory, user):
    order1 = order_factory(user=user)
    order2 = order_factory(user=user)
    assert order1.user == order2.user and order1.city != order2.city


@pytest.mark.django_db
def test_order_str_representation(order):
    assert str(order) == f"{order.user} -- {order.status}"


@pytest.mark.django_db
def test_order_can_be_created_without_a_user(book_factory):
    # Generated with AI, reviewed and modified
    order = Order.objects.create(
        email="guest@example.com", total_price=Decimal("20.00")
    )
    assert order.user is None
    assert order.email == "guest@example.com"


@pytest.mark.django_db
def test_order_item_get_total_multiplies_price_by_quantity(order_factory, book_factory):
    # Generated with AI, reviewed and modified
    order = order_factory()
    book = book_factory(price=Decimal("15.50"))
    item = OrderItem.objects.create(
        order=order, book=book, price=Decimal("15.50"), quantity=3
    )
    assert item.get_total() == Decimal("46.50")


@pytest.mark.django_db
def test_order_item_str_representation(order_factory, book_factory):
    # Generated with AI, reviewed and modified
    order = order_factory()
    book = book_factory()
    item = OrderItem.objects.create(
        order=order, book=book, price=book.price, quantity=1
    )
    assert str(item) == f"{order} -- {book} -- {book.price}"


@pytest.mark.django_db
def test_order_default_quantity_for_order_item_is_one(order_factory, book_factory):
    # Generated with AI, reviewed and modified
    order = order_factory()
    book = book_factory()
    item = OrderItem.objects.create(order=order, book=book, price=book.price)
    assert item.quantity == 1
