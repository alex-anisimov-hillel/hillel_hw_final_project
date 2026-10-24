import pytest
from django.core.cache import cache
from pytest_factoryboy import register
from book_shop.factory.factories import (
    CategoryFactory,
    BookFactory,
    UserFactory,
    PaymentFactory,
    OrderFactory,
)

register(CategoryFactory)
register(BookFactory)
register(UserFactory)
register(PaymentFactory)
register(OrderFactory)


@pytest.fixture(autouse=True)
def clear_cache():
    """Reset the Redis cache around every test.

    DRF's anonymous throttle (10/min) keeps its counters in the cache, so state
    leaking between tests - or between consecutive pytest runs - made tests fail
    with HTTP 429.
    """
    cache.clear()
    yield
    cache.clear()
