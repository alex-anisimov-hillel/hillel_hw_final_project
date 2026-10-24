import hashlib
import hmac
import json
import time

import pytest
import responses
from django.core.cache import cache
from django.core.management import call_command

from books.cache_utils import book_cache_key
from warehouse import tasks
from warehouse.tests.conftest import API, SECRET

URL = "/api/warehouse/webhook/"


def signed(client, payload, secret=SECRET, ts=None, signature=None):
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ts = str(int(time.time()) if ts is None else ts)
    sig = (
        signature
        or "sha256="
        + hmac.new(
            secret.encode(), ts.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
    )
    return client.post(
        URL,
        data=body,
        content_type="application/json",
        HTTP_X_WEBHOOK_TIMESTAMP=ts,
        HTTP_X_WEBHOOK_SIGNATURE=sig,
    )


def event(book_id, available, event_id="evt-1", name="stock.changed"):
    return {
        "id": event_id,
        "event": name,
        "data": {"items": [{"book_id": book_id, "available": available}]},
    }


@pytest.mark.django_db
class TestWebhook:
    def test_stock_changed_updates_book_and_drops_cache(self, client, book):
        cache.set(book_cache_key(book.pk), "stale")
        resp = signed(client, event(book.pk, 7))
        book.refresh_from_db()
        assert resp.status_code == 204 and book.stock == 7
        assert cache.get(book_cache_key(book.pk)) is None

    def test_bad_signature_rejected(self, client, book):
        before = book.stock
        resp = signed(client, event(book.pk, 7), signature="sha256=" + "0" * 64)
        book.refresh_from_db()
        assert resp.status_code == 401 and book.stock == before

    def test_wrong_secret_rejected(self, client, book):
        assert signed(client, event(book.pk, 7), secret="other").status_code == 401

    def test_tampered_body_rejected(self, client, book):
        body = json.dumps(event(book.pk, 7), sort_keys=True).encode()
        ts = str(int(time.time()))
        sig = (
            "sha256="
            + hmac.new(
                SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256
            ).hexdigest()
        )
        resp = client.post(
            URL,
            data=body.replace(b"7", b"9"),
            content_type="application/json",
            HTTP_X_WEBHOOK_TIMESTAMP=ts,
            HTTP_X_WEBHOOK_SIGNATURE=sig,
        )
        assert resp.status_code == 401

    def test_stale_timestamp_rejected_as_replay(self, client, book):
        assert (
            signed(client, event(book.pk, 7), ts=int(time.time()) - 3600).status_code
            == 401
        )

    def test_missing_headers_rejected(self, client):
        assert (
            client.post(URL, data="{}", content_type="application/json").status_code
            == 401
        )

    def test_duplicate_event_id_is_processed_once(self, client, book):
        signed(client, event(book.pk, 7, "same"))
        book.stock = 99
        book.save()
        assert signed(client, event(book.pk, 7, "same")).status_code == 204
        book.refresh_from_db()
        assert book.stock == 99  # second delivery ignored

    def test_unknown_event_is_accepted_and_ignored(self, client, book):
        assert (
            signed(client, event(book.pk, 7, name="something.else")).status_code == 202
        )

    def test_malformed_payload(self, client):
        assert signed(client, {"nope": 1}).status_code == 400

    def test_unknown_book_is_skipped(self, client):
        assert signed(client, event(999999, 5)).status_code == 204

    def test_not_configured_returns_503(self, client, settings):
        settings.WAREHOUSE_WEBHOOK_SECRET = ""
        assert signed(client, {"id": "x", "event": "e", "data": {}}).status_code == 503

    def test_low_stock_sends_alert_email(self, client, settings, mailoutbox):
        settings.LOW_STOCK_ALERT_EMAILS = ["ops@example.com"]
        payload = {
            "id": "low-1",
            "event": "stock.low",
            "data": {"items": [{"book_id": 1, "title": "Dune", "available": 2}]},
        }
        assert signed(client, payload).status_code == 204
        assert len(mailoutbox) == 1 and "Dune" in mailoutbox[0].body


@pytest.mark.django_db
class TestStockSync:
    def test_sync_updates_only_tracked_books(self, mocked, book_factory):
        tracked, untracked = book_factory(stock=50), book_factory(stock=33)
        mocked.add(
            responses.POST,
            f"{API}/stock/availability/",
            json={
                "items": [
                    {"book_id": tracked.pk, "available": 4, "tracked": True},
                    {"book_id": untracked.pk, "available": 0, "tracked": False},
                ]
            },
        )
        assert tasks.sync_stock_levels() == {"books": 2, "changed": 1}
        tracked.refresh_from_db(), untracked.refresh_from_db()
        assert (tracked.stock, untracked.stock) == (4, 33)

    def test_sync_command(self, mocked, book, capsys):
        mocked.add(
            responses.POST,
            f"{API}/stock/availability/",
            json={"items": [{"book_id": book.pk, "available": 1, "tracked": True}]},
        )
        call_command("sync_stock")
        book.refresh_from_db()
        assert book.stock == 1 and "Stock sync done" in capsys.readouterr().out

    def test_sync_skipped_when_disabled(self, settings):
        settings.WAREHOUSE_ENABLED = False
        assert tasks.sync_stock_levels() == {"skipped": True}


@pytest.mark.django_db
class TestSeedCommand:
    def test_seeds_only_untracked_books_with_stock(self, mocked, book_factory, capsys):
        new, known, empty = (
            book_factory(stock=5),
            book_factory(stock=8),
            book_factory(stock=0),
        )
        mocked.add(
            responses.POST,
            f"{API}/stock/availability/",
            json={
                "items": [
                    {"book_id": new.pk, "available": 0, "tracked": False},
                    {"book_id": known.pk, "available": 8, "tracked": True},
                    {"book_id": empty.pk, "available": 0, "tracked": False},
                ]
            },
        )
        mocked.add(responses.POST, f"{API}/stock/restock/", json={}, status=201)
        call_command("seed_warehouse", email="ops@example.com", password="x")
        restocks = [c for c in mocked.calls if c.request.url.endswith("/restock/")]
        assert len(restocks) == 1
        assert json.loads(restocks[0].request.body)["book_id"] == new.pk

    def test_dry_run_changes_nothing(self, mocked, book_factory):
        book = book_factory(stock=5)
        mocked.add(
            responses.POST,
            f"{API}/stock/availability/",
            json={"items": [{"book_id": book.pk, "available": 0, "tracked": False}]},
        )
        call_command(
            "seed_warehouse", email="ops@example.com", password="x", dry_run=True
        )
        assert not [c for c in mocked.calls if c.request.url.endswith("/restock/")]

    def test_requires_credentials(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command("seed_warehouse", email="", password="")
