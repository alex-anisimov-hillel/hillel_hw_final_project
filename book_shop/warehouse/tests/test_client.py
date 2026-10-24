import pytest
import requests
import responses

from warehouse.client import WarehouseClient
from warehouse.exceptions import (
    InsufficientStock,
    ReservationConflict,
    WarehouseAuthError,
    WarehouseBadRequest,
    WarehouseUnavailable,
)
from warehouse.tests.conftest import API, make_jwt

RESERVE = f"{API}/reservations/"
ITEMS = [{"book_id": 1, "quantity": 2}]


@pytest.mark.django_db
class TestAuthHandling:
    def test_token_is_cached_between_calls(self, mocked):
        mocked.add(responses.POST, RESERVE, json={"id": "r1"}, status=201)
        client = WarehouseClient()
        client.reserve(1, ITEMS)
        client.reserve(2, ITEMS)
        logins = [c for c in mocked.calls if c.request.url.endswith("/auth/token/")]
        assert len(logins) == 1
        assert (
            mocked.calls[1]
            .request.headers["Authorization"]
            .startswith("Bearer header.")
        )

    def test_token_shared_across_client_instances(self, mocked):
        mocked.add(responses.POST, RESERVE, json={"id": "r1"}, status=201)
        WarehouseClient().reserve(1, ITEMS)
        WarehouseClient().reserve(2, ITEMS)
        assert (
            len([c for c in mocked.calls if c.request.url.endswith("/auth/token/")])
            == 1
        )

    def test_expired_access_token_uses_refresh(self, mocked):
        mocked.replace(
            responses.POST,
            f"{API}/auth/token/",
            json={
                "access": make_jwt(ttl=1),
                "refresh": make_jwt(86400),
            },  # access ~expired (margin 30s)
        )
        mocked.add(
            responses.POST, f"{API}/auth/token/refresh/", json={"access": make_jwt()}
        )
        mocked.add(responses.POST, RESERVE, json={"id": "r1"}, status=201)
        WarehouseClient().reserve(1, ITEMS)
        WarehouseClient().reserve(2, ITEMS)
        urls = [c.request.url for c in mocked.calls]
        assert any(u.endswith("/auth/token/refresh/") for u in urls)

    def test_401_triggers_one_relogin_then_succeeds(self, mocked):
        mocked.add(responses.POST, RESERVE, status=401, json={})
        mocked.add(responses.POST, RESERVE, json={"id": "r1"}, status=201)
        assert WarehouseClient().reserve(1, ITEMS) == {"id": "r1"}
        assert (
            len([c for c in mocked.calls if c.request.url.endswith("/auth/token/")])
            == 2
        )

    def test_persistent_401_is_auth_error(self, mocked):
        mocked.add(responses.POST, RESERVE, status=401, json={"detail": "no"})
        with pytest.raises(WarehouseAuthError):
            WarehouseClient().reserve(1, ITEMS)

    def test_bad_credentials(self, mocked):
        mocked.replace(responses.POST, f"{API}/auth/token/", status=401, json={})
        with pytest.raises(WarehouseAuthError):
            WarehouseClient().reserve(1, ITEMS)

    def test_403_is_auth_error(self, mocked):
        mocked.add(responses.POST, RESERVE, status=403, json={"detail": "forbidden"})
        with pytest.raises(WarehouseAuthError):
            WarehouseClient().reserve(1, ITEMS)


@pytest.mark.django_db
class TestErrorMapping:
    def test_insufficient_stock(self, mocked):
        shortages = [{"book_id": 1, "requested": 5, "available": 1}]
        mocked.add(
            responses.POST,
            RESERVE,
            status=409,
            json={"code": "insufficient_stock", "shortages": shortages},
        )
        with pytest.raises(InsufficientStock) as exc:
            WarehouseClient().reserve(1, ITEMS)
        assert exc.value.shortages == shortages

    def test_other_409_is_conflict(self, mocked):
        mocked.add(
            responses.POST,
            f"{API}/reservations/abc/confirm/",
            status=409,
            json={"code": "invalid_reservation_state", "detail": "nope"},
        )
        with pytest.raises(ReservationConflict):
            WarehouseClient().confirm("abc")

    def test_400_is_bad_request_with_payload(self, mocked):
        mocked.add(
            responses.POST, RESERVE, status=400, json={"code": "validation_error"}
        )
        with pytest.raises(WarehouseBadRequest) as exc:
            WarehouseClient().reserve(1, ITEMS)
        assert exc.value.payload["code"] == "validation_error"


@pytest.mark.django_db
class TestResilience:
    def test_5xx_is_retried_then_succeeds(self, mocked):
        mocked.add(responses.POST, RESERVE, status=503)
        mocked.add(responses.POST, RESERVE, json={"id": "r1"}, status=201)
        assert WarehouseClient().reserve(1, ITEMS)["id"] == "r1"

    def test_persistent_5xx_is_unavailable(self, mocked):
        mocked.add(responses.POST, RESERVE, status=503)
        with pytest.raises(WarehouseUnavailable):
            WarehouseClient().reserve(1, ITEMS)
        assert len([c for c in mocked.calls if c.request.url == RESERVE]) == 2

    def test_timeout_and_connection_errors_are_unavailable(self, mocked):
        mocked.add(responses.POST, RESERVE, body=requests.ConnectTimeout("slow"))
        with pytest.raises(WarehouseUnavailable):
            WarehouseClient().reserve(1, ITEMS)

    def test_500_from_endpoint_maps_to_unavailable(self, mocked):
        mocked.add(responses.POST, RESERVE, status=500, json={})
        with pytest.raises(WarehouseUnavailable):
            WarehouseClient().reserve(1, ITEMS)

    def test_restock_is_never_retried(self, mocked):
        mocked.add(responses.POST, f"{API}/stock/restock/", status=503)
        with pytest.raises(WarehouseUnavailable):
            WarehouseClient().restock(1, 5)
        assert (
            len([c for c in mocked.calls if c.request.url.endswith("/restock/")]) == 1
        )

    def test_request_id_header_is_sent(self, mocked):
        from warehouse.request_id import request_id_var

        mocked.add(responses.POST, RESERVE, json={"id": "r1"}, status=201)
        token = request_id_var.set("trace-me-123")
        try:
            WarehouseClient().reserve(1, ITEMS)
        finally:
            request_id_var.reset(token)
        assert mocked.calls[-1].request.headers["X-Request-ID"] == "trace-me-123"

    def test_availability_map(self, mocked):
        mocked.add(
            responses.POST,
            f"{API}/stock/availability/",
            json={
                "items": [
                    {"book_id": 1, "available": 4, "tracked": True},
                    {"book_id": 2, "available": 0, "tracked": False},
                ]
            },
        )
        result = WarehouseClient().get_availability([1, 2])
        assert result[1]["available"] == 4 and result[2]["tracked"] is False

    def test_find_reservation(self, mocked):
        mocked.add(responses.GET, RESERVE, json={"results": [{"id": "r9"}]})
        assert WarehouseClient().find_reservation(5)["id"] == "r9"
        mocked.replace(responses.GET, RESERVE, json={"results": []})
        assert WarehouseClient().find_reservation(5) is None
