"""Real-database concurrency checks. Skipped on SQLite (it has no row locks)."""

import threading

import pytest
from django.db import connection, connections

from warehouse_mgmt import services
from warehouse_mgmt.exceptions import InsufficientStock
from warehouse_mgmt.models import StockItem, StockReservation

pytestmark = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="needs PostgreSQL row locking"
)


def run_in_threads(targets):
    results, lock = [], threading.Lock()
    barrier = threading.Barrier(len(targets))

    def wrap(fn):
        def inner():
            try:
                barrier.wait()
                outcome = fn()
            except Exception as exc:  # collected for assertions
                outcome = exc
            finally:
                connections.close_all()
            with lock:
                results.append(outcome)

        return inner

    threads = [threading.Thread(target=wrap(t)) for t in targets]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_never_oversell(main_wh):
    StockItem.objects.create(warehouse=main_wh, book_id=1, quantity=5)
    results = run_in_threads(
        [
            lambda i=i: services.reserve_stock(order_id=i, items=[(1, 1)])
            for i in range(1, 13)
        ]
    )
    ok = [r for r in results if isinstance(r, tuple)]
    failed = [r for r in results if isinstance(r, InsufficientStock)]
    assert len(ok) == 5 and len(failed) == 7
    item = StockItem.objects.get(book_id=1)
    assert (item.quantity, item.reserved) == (5, 5)


@pytest.mark.django_db(transaction=True)
def test_concurrent_retries_of_same_order_create_one_reservation(main_wh):
    StockItem.objects.create(warehouse=main_wh, book_id=1, quantity=10)
    results = run_in_threads(
        [lambda: services.reserve_stock(order_id=42, items=[(1, 3)]) for _ in range(6)]
    )
    assert all(isinstance(r, tuple) for r in results), results
    assert sum(1 for r in results if r[1]) == 1  # exactly one creator
    assert StockReservation.objects.filter(order_id=42).count() == 1
    assert StockItem.objects.get(book_id=1).reserved == 3


@pytest.mark.django_db(transaction=True)
def test_concurrent_restock_of_new_book_does_not_lose_updates(main_wh):
    results = run_in_threads(
        [lambda: services.restock(book_id=9, quantity=2) for _ in range(8)]
    )
    assert not [r for r in results if isinstance(r, Exception)], results
    assert StockItem.objects.get(book_id=9).quantity == 16
