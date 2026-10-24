import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from warehouse_mgmt.models import StockItem, StockReservation
from users.models import User

RESERVATIONS = "/api/reservations/"


@pytest.mark.django_db
class TestAuth:
    def test_anonymous_gets_401(self):
        assert APIClient().get("/api/stock/1/").status_code == 401

    def test_jwt_flow_with_groups_claim(self, service_user):
        client = APIClient()
        resp = client.post(
            "/api/auth/token/",
            {"email": "projecta@example.com", "password": "pass12345!"},
        )
        assert resp.status_code == 200 and {"access", "refresh"} <= set(resp.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        me = client.get("/api/auth/me/")
        assert me.status_code == 200
        assert me.data["groups"] == ["ServiceAccount"]
        assert "warehouse_mgmt.manage_reservation" in me.data["permissions"]
        refreshed = client.post(
            "/api/auth/token/refresh/", {"refresh": resp.data["refresh"]}
        )
        assert refreshed.status_code == 200 and "access" in refreshed.data

    def test_wrong_password_is_401(self, service_user):
        resp = APIClient().post(
            "/api/auth/token/", {"email": "projecta@example.com", "password": "bad"}
        )
        assert resp.status_code == 401

    def test_user_without_role_is_403(self, api, nobody):
        assert api(nobody).get("/api/stock/1/").status_code == 403


@pytest.mark.django_db
class TestAvailabilityApi:
    def test_single_and_bulk(self, api, service_user, stock):
        stock(1, 10)
        client = api(service_user)
        assert client.get("/api/stock/1/").data["available"] == 10
        bulk = client.post(
            "/api/stock/availability/", {"book_ids": [1, 2]}, format="json"
        )
        assert bulk.status_code == 200
        assert [i["available"] for i in bulk.data["items"]] == [10, 0]

    def test_bulk_validation(self, api, service_user):
        resp = api(service_user).post(
            "/api/stock/availability/", {"book_ids": []}, format="json"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestReservationApi:
    def payload(self, order_id=1, book_id=1, quantity=2):
        return {
            "order_id": order_id,
            "items": [{"book_id": book_id, "quantity": quantity}],
        }

    def test_create_confirm_flow(self, api, service_user, stock):
        item = stock(1, 10)
        client = api(service_user)
        created = client.post(RESERVATIONS, self.payload(), format="json")
        assert created.status_code == 201
        assert created.data["lines"] == [
            {"book_id": 1, "quantity": 2, "warehouse": "main"}
        ]
        rid = created.data["id"]
        assert client.get(f"{RESERVATIONS}{rid}/").data["status"] == "pending"
        confirmed = client.post(f"{RESERVATIONS}{rid}/confirm/")
        assert confirmed.status_code == 200 and confirmed.data["status"] == "confirmed"
        item.refresh_from_db()
        assert (item.quantity, item.reserved) == (8, 0)

    def test_replay_returns_200_not_a_second_reservation(
        self, api, service_user, stock
    ):
        stock(1, 10)
        client = api(service_user)
        assert (
            client.post(RESERVATIONS, self.payload(), format="json").status_code == 201
        )
        assert (
            client.post(RESERVATIONS, self.payload(), format="json").status_code == 200
        )
        assert StockReservation.objects.count() == 1

    def test_insufficient_stock_is_409_with_details(self, api, service_user, stock):
        stock(1, 1)
        resp = api(service_user).post(
            RESERVATIONS, self.payload(quantity=5), format="json"
        )
        assert resp.status_code == 409
        assert resp.data["code"] == "insufficient_stock"
        assert resp.data["shortages"] == [
            {"book_id": 1, "requested": 5, "available": 1}
        ]
        assert "request_id" in resp.data

    def test_error_message_is_localised(self, api, service_user, stock):
        stock(1, 1)
        resp = api(service_user).post(
            RESERVATIONS,
            self.payload(quantity=5),
            format="json",
            HTTP_ACCEPT_LANGUAGE="uk",
        )
        assert resp.status_code == 409
        assert (
            resp.data["detail"] == "Недостатньо товару на складі для виконання запиту."
        )

    def test_validation_error(self, api, service_user):
        resp = api(service_user).post(
            RESERVATIONS, {"order_id": 1, "items": []}, format="json"
        )
        assert resp.status_code == 400

    def test_operator_cannot_reserve(self, api, operator, stock):
        stock(1, 10)
        assert (
            api(operator).post(RESERVATIONS, self.payload(), format="json").status_code
            == 403
        )

    def test_operator_can_list_but_not_cancel(self, api, operator, service_user, stock):
        stock(1, 10)
        rid = (
            api(service_user)
            .post(RESERVATIONS, self.payload(), format="json")
            .data["id"]
        )
        client = api(operator)
        assert client.get(RESERVATIONS).status_code == 200
        assert client.post(f"{RESERVATIONS}{rid}/cancel/").status_code == 403

    def test_other_service_account_cannot_touch_foreign_reservation(
        self, api, service_user, other_service_user, stock
    ):
        stock(1, 10)
        rid = (
            api(service_user)
            .post(RESERVATIONS, self.payload(), format="json")
            .data["id"]
        )
        assert (
            api(other_service_user).post(f"{RESERVATIONS}{rid}/cancel/").status_code
            == 403
        )

    def test_manager_can_cancel_foreign_reservation(
        self, api, service_user, manager, stock
    ):
        stock(1, 10)
        rid = (
            api(service_user)
            .post(RESERVATIONS, self.payload(), format="json")
            .data["id"]
        )
        assert (
            api(manager).post(f"{RESERVATIONS}{rid}/cancel/").data["status"]
            == "cancelled"
        )

    def test_cancel_after_confirm_is_409(self, api, service_user, stock):
        stock(1, 10)
        client = api(service_user)
        rid = client.post(RESERVATIONS, self.payload(), format="json").data["id"]
        client.post(f"{RESERVATIONS}{rid}/confirm/")
        resp = client.post(f"{RESERVATIONS}{rid}/cancel/")
        assert (
            resp.status_code == 409 and resp.data["code"] == "invalid_reservation_state"
        )

    def test_unknown_reservation_404(self, api, service_user):
        resp = api(service_user).post(
            f"{RESERVATIONS}00000000-0000-0000-0000-000000000000/confirm/"
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestManagementApi:
    def test_restock_by_operator(self, api, operator):
        resp = api(operator).post(
            "/api/stock/restock/",
            {"book_id": 3, "quantity": 15, "title": "Emma"},
            format="json",
        )
        assert resp.status_code == 201 and resp.data["quantity"] == 15
        assert StockItem.objects.get(book_id=3).title == "Emma"

    def test_service_account_cannot_restock(self, api, service_user):
        resp = api(service_user).post(
            "/api/stock/restock/", {"book_id": 3, "quantity": 1}, format="json"
        )
        assert resp.status_code == 403

    def test_restock_unknown_warehouse_is_400(self, api, operator):
        resp = api(operator).post(
            "/api/stock/restock/",
            {"book_id": 3, "quantity": 1, "warehouse": "zzz"},
            format="json",
        )
        assert resp.status_code == 400 and resp.data["code"] == "unknown_warehouse"

    def test_adjust_is_manager_only(self, api, operator, manager, stock):
        stock(1, 10)
        body = {"book_id": 1, "delta": -3, "note": "damaged"}
        assert (
            api(operator).post("/api/stock/adjust/", body, format="json").status_code
            == 403
        )
        resp = api(manager).post("/api/stock/adjust/", body, format="json")
        assert resp.status_code == 200 and resp.data["quantity"] == 7

    def test_adjust_zero_delta_rejected(self, api, manager, stock):
        stock(1, 10)
        resp = api(manager).post(
            "/api/stock/adjust/", {"book_id": 1, "delta": 0, "note": "x"}, format="json"
        )
        assert resp.status_code == 400

    def test_stock_item_quantity_is_read_only_via_crud(self, api, manager, stock):
        item = stock(1, 10)
        resp = api(manager).patch(
            f"/api/stock-items/{item.pk}/",
            {"quantity": 999, "title": "New"},
            format="json",
        )
        item.refresh_from_db()
        assert resp.status_code == 200 and (item.quantity, item.title) == (10, "New")

    def test_stock_item_delete_not_allowed(self, api, manager, stock):
        item = stock(1, 10)
        # No role has delete_stockitem and the viewset exposes no DELETE handler either.
        assert api(manager).delete(f"/api/stock-items/{item.pk}/").status_code == 403

    def test_warehouse_crud_permissions(self, api, manager, operator):
        body = {"name": "North", "code": "north"}
        assert (
            api(operator).post("/api/warehouses/", body, format="json").status_code
            == 403
        )
        assert (
            api(manager).post("/api/warehouses/", body, format="json").status_code
            == 201
        )
        assert api(operator).get("/api/warehouses/").status_code == 200

    def test_movements_filter_and_low_stock_filter(self, api, manager, stock):
        stock(1, 5, low_stock_threshold=10)
        stock(2, 50)
        client = api(manager)
        items = client.get("/api/stock-items/?low_stock=true").data["results"]
        assert [i["book_id"] for i in items] == [1]
        client.post("/api/stock/restock/", {"book_id": 2, "quantity": 1}, format="json")
        moves = client.get("/api/movements/?book_id=2&kind=restock").data["results"]
        assert len(moves) == 1 and moves[0]["quantity_delta"] == 1


@pytest.mark.django_db
class TestMisc:
    def test_health_is_public(self):
        resp = APIClient().get("/health/")
        assert resp.status_code == 200 and resp.data["status"] == "ok"

    def test_request_id_echoed_and_generated(self):
        client = APIClient()
        assert (
            client.get("/health/", HTTP_X_REQUEST_ID="abc-123")["X-Request-ID"]
            == "abc-123"
        )
        generated = client.get("/health/", HTTP_X_REQUEST_ID="bad id\nwith newline")[
            "X-Request-ID"
        ]
        assert len(generated) == 32 and generated != "bad id\nwith newline"

    def test_groups_and_permissions_are_provisioned(self, db):
        expected = {"WarehouseManager", "Operator", "ServiceAccount"}
        assert expected <= set(Group.objects.values_list("name", flat=True))
        perms = set(
            Group.objects.get(name="ServiceAccount").permissions.values_list(
                "codename", flat=True
            )
        )
        assert perms == {
            "view_stockitem",
            "view_stockreservation",
            "manage_reservation",
        }

    def test_dashboard_requires_login_and_permission(self, client, manager, nobody):
        assert client.get("/").status_code == 302  # redirected to login
        client.force_login(nobody)
        assert client.get("/").status_code == 403  # logged in but no role
        client.force_login(manager)
        assert client.get("/").status_code == 200
        assert client.get("/reservations/").status_code == 200

    def test_dashboard_search_and_language(self, client, manager, stock):
        stock(1, 10, title="Dune")
        stock(2, 10, title="Emma")
        client.force_login(manager)
        resp = client.get("/?q=dune")
        assert [i.title for i in resp.context["items"]] == ["Dune"]
        assert (
            "Рівні запасів"
            in client.get("/", HTTP_ACCEPT_LANGUAGE="uk").content.decode()
        )

    def test_openapi_schema_builds(self, client):
        assert client.get("/api/schema/").status_code == 200


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_requires_email(self):
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="x")

    def test_email_is_normalised_and_unique_login(self):
        user = User.objects.create_user(email="A@EXAMPLE.com", password="x")
        assert user.email == "A@example.com" and user.check_password("x")

    def test_create_superuser_flags(self):
        admin = User.objects.create_superuser(email="root@example.com", password="x")
        assert admin.is_staff and admin.is_superuser
        with pytest.raises(ValueError):
            User.objects.create_superuser(
                email="r2@example.com", password="x", is_staff=False
            )

    def test_bootstrap_service_account_command(self, db):
        from django.core.management import call_command

        call_command(
            "bootstrap_service_account", email="svc@example.com", password="s3cret-pass"
        )
        call_command(
            "bootstrap_service_account",
            email="svc@example.com",
            password="rotated-pass",
        )
        user = User.objects.get(email="svc@example.com")
        assert user.check_password("rotated-pass")
        assert list(user.groups.values_list("name", flat=True)) == ["ServiceAccount"]
