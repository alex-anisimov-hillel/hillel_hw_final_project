import json

import pytest
import requests
import responses
from celery.exceptions import Retry
from django.utils import timezone

from warehouse_mgmt import services, tasks
from warehouse_mgmt.models import StockReservation
from warehouse_mgmt.webhooks import WebhookDeliveryError, deliver, sign

URL = "http://projecta.test/api/warehouse/webhook/"
SECRET = "test-webhook-secret"


@pytest.mark.django_db
class TestWebhookDelivery:
    @responses.activate
    def test_payload_is_signed_and_carries_request_id(self):
        responses.add(responses.POST, URL, status=204)
        result = deliver("stock.changed", {"items": []}, event_id="evt1")
        assert result["status"] == "delivered"
        request = responses.calls[0].request
        ts = request.headers["X-Webhook-Timestamp"]
        assert request.headers["X-Webhook-Signature"] == sign(SECRET, ts, request.body)
        assert json.loads(request.body)["id"] == "evt1"
        assert "X-Request-ID" in request.headers

    @responses.activate
    def test_5xx_and_network_errors_are_retryable(self):
        responses.add(responses.POST, URL, status=503)
        with pytest.raises(WebhookDeliveryError):
            deliver("stock.changed", {})
        responses.replace(responses.POST, URL, body=requests.ConnectionError("down"))
        with pytest.raises(WebhookDeliveryError):
            deliver("stock.changed", {})

    @responses.activate
    def test_4xx_is_permanent(self):
        responses.add(responses.POST, URL, status=401)
        assert deliver("stock.changed", {}) == {
            "status": "rejected",
            "http_status": 401,
        }

    def test_disabled_without_url(self, settings):
        settings.PROJECTA_WEBHOOK_URL = ""
        assert deliver("stock.changed", {}) == {"status": "disabled"}

    @responses.activate
    def test_task_retries_on_failure(self):
        responses.add(responses.POST, URL, status=500)
        with pytest.raises(Retry):
            tasks.send_webhook.apply(args=["stock.changed", {}], throw=True).get()


@pytest.mark.django_db
class TestStockChangeNotifications:
    @responses.activate
    def test_reserve_triggers_stock_changed_webhook_after_commit(
        self, stock, django_capture_on_commit_callbacks
    ):
        responses.add(responses.POST, URL, status=204)
        stock(1, 10)
        with django_capture_on_commit_callbacks(execute=True):
            services.reserve_stock(order_id=1, items=[(1, 4)])
        body = json.loads(responses.calls[0].request.body)
        assert body["event"] == "stock.changed"
        assert body["data"]["items"] == [
            {"book_id": 1, "available": 6, "quantity": 10, "reserved": 4}
        ]

    @responses.activate
    def test_no_webhook_when_transaction_rolls_back(
        self, stock, django_capture_on_commit_callbacks
    ):
        stock(1, 1)
        with django_capture_on_commit_callbacks(execute=True):
            with pytest.raises(Exception):
                services.reserve_stock(order_id=1, items=[(1, 5)])
        assert len(responses.calls) == 0

    def test_broker_failure_does_not_break_stock_change(
        self, stock, django_capture_on_commit_callbacks, monkeypatch
    ):
        def boom(*a, **k):
            raise RuntimeError("broker down")

        monkeypatch.setattr(tasks.notify_stock_changed, "delay", boom)
        stock(1, 10)
        with django_capture_on_commit_callbacks(execute=True):
            reservation, created = services.reserve_stock(order_id=1, items=[(1, 4)])
        assert created and StockReservation.objects.filter(pk=reservation.pk).exists()


@pytest.mark.django_db
class TestPeriodicTasks:
    def test_expire_stale_reservations(self, stock):
        item = stock(1, 10)
        old, _ = services.reserve_stock(order_id=1, items=[(1, 3)])
        fresh, _ = services.reserve_stock(order_id=2, items=[(1, 2)])
        StockReservation.objects.filter(pk=old.pk).update(
            expires_at=timezone.now() - timezone.timedelta(minutes=5)
        )
        assert tasks.expire_stale_reservations() == {"expired": 1}
        item.refresh_from_db()
        assert item.reserved == 2
        assert StockReservation.objects.get(pk=fresh.pk).status == "pending"

    @responses.activate
    def test_check_low_stock_sends_webhook(self, stock):
        responses.add(responses.POST, URL, status=204)
        stock(1, 3, title="Dune", low_stock_threshold=10)
        stock(2, 100)
        assert tasks.check_low_stock() == {"low_stock_items": 1}
        body = json.loads(responses.calls[0].request.body)
        assert body["event"] == "stock.low" and body["data"]["items"][0]["book_id"] == 1

    @responses.activate
    def test_check_low_stock_silent_when_fine(self, stock):
        stock(1, 100)
        assert tasks.check_low_stock() == {"low_stock_items": 0}
        assert len(responses.calls) == 0

    def test_generate_stock_report(self, stock, settings, tmp_path):
        settings.REPORTS_DIR = tmp_path
        stock(1, 10, title="Dune")
        result = tasks.generate_stock_report()
        assert result["rows"] == 1
        assert "Dune" in open(result["report_path"], encoding="utf-8").read()
