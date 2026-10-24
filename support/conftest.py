import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework.test import APIClient

from warehouse_mgmt.models import StockItem, Warehouse
from users.models import User
from users.roles import OPERATOR, SERVICE_ACCOUNT, WAREHOUSE_MANAGER


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def _user(email, role=None, **extra):
    user = User.objects.create_user(email=email, password="pass12345!", **extra)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


@pytest.fixture
def manager(db):
    return _user("manager@example.com", WAREHOUSE_MANAGER)


@pytest.fixture
def operator(db):
    return _user("operator@example.com", OPERATOR)


@pytest.fixture
def service_user(db):
    return _user("projecta@example.com", SERVICE_ACCOUNT)


@pytest.fixture
def other_service_user(db):
    return _user("other-service@example.com", SERVICE_ACCOUNT)


@pytest.fixture
def nobody(db):
    return _user("nobody@example.com")


@pytest.fixture
def api(db):
    def make(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return make


@pytest.fixture(autouse=True)
def main_wh(db):
    """Default warehouse (data migration); transactional tests flush it."""
    warehouse, _ = Warehouse.objects.get_or_create(
        code="main", defaults={"name": "Main warehouse", "priority": 10}
    )
    return warehouse


@pytest.fixture
def second_wh(db):
    return Warehouse.objects.create(name="Second", code="second", priority=50)


@pytest.fixture
def stock(main_wh):
    def make(book_id, quantity, warehouse=None, **kw):
        return StockItem.objects.create(
            warehouse=warehouse or main_wh, book_id=book_id, quantity=quantity, **kw
        )

    return make
