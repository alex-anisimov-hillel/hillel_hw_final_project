"""HTTP client for the warehouse service (ProjectB).

* JWT auth with a cached access/refresh pair (shared by all workers through Django's
  cache), transparent refresh and one re-login on HTTP 401.
* Timeouts on every call, bounded retries with exponential backoff - but only for
  calls that are safe to repeat (reserve/confirm/cancel are idempotent on the warehouse
  side, keyed by order id).
* Every failure is mapped to a small exception hierarchy (``warehouse.exceptions``).
* Each call is logged with the correlation id sent as ``X-Request-ID``.
"""

import base64
import hashlib
import json
import logging
import time

import requests
from django.conf import settings
from django.core.cache import cache

from warehouse.exceptions import (
    InsufficientStock,
    ReservationConflict,
    WarehouseAuthError,
    WarehouseBadRequest,
    WarehouseError,
    WarehouseUnavailable,
)
from warehouse.request_id import HEADER as REQUEST_ID_HEADER
from warehouse.request_id import get_request_id

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {502, 503, 504}
TOKEN_SAFETY_MARGIN = 30  # seconds before real expiry at which we stop trusting a token


def _jwt_exp(token: str, default_ttl: int = 60) -> float:
    """Read ``exp`` from a JWT payload (no verification - we only need the lifetime)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (IndexError, ValueError, KeyError, TypeError):
        return time.time() + default_ttl


class WarehouseClient:
    def __init__(
        self,
        base_url=None,
        email=None,
        password=None,
        timeout=None,
        max_attempts=None,
        session=None,
    ):
        self.base_url = (base_url or settings.WAREHOUSE_API_URL).rstrip("/")
        self.email = email or settings.WAREHOUSE_SERVICE_EMAIL
        self.password = password or settings.WAREHOUSE_SERVICE_PASSWORD
        self.timeout = timeout or settings.WAREHOUSE_TIMEOUT
        self.max_attempts = max_attempts or settings.WAREHOUSE_MAX_ATTEMPTS
        self.session = session or requests.Session()
        digest = hashlib.sha1(f"{self.base_url}|{self.email}".encode()).hexdigest()[:12]
        self._cache_key = f"warehouse:jwt:{digest}"  # one entry per (url, account)

    # ------------------------------------------------------------------ tokens
    def _store_tokens(self, access, refresh):
        entry = {
            "access": access,
            "access_exp": _jwt_exp(access),
            "refresh": refresh,
            "refresh_exp": _jwt_exp(refresh) if refresh else 0,
        }
        ttl = max(int(max(entry["access_exp"], entry["refresh_exp"]) - time.time()), 1)
        cache.set(self._cache_key, entry, ttl)
        return entry

    def _invalidate_token(self):
        cache.delete(self._cache_key)

    def _token_request(self, path, payload):
        url = f"{self.base_url}/auth/token/{path}"
        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={REQUEST_ID_HEADER: get_request_id()},
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise WarehouseUnavailable(f"auth request failed: {exc}") from exc
        return response

    def _access_token(self) -> str:
        now = time.time()
        entry = cache.get(self._cache_key)
        if entry and entry["access_exp"] - TOKEN_SAFETY_MARGIN > now:
            return entry["access"]
        if (
            entry
            and entry.get("refresh")
            and entry["refresh_exp"] - TOKEN_SAFETY_MARGIN > now
        ):
            response = self._token_request("refresh/", {"refresh": entry["refresh"]})
            if response.status_code == 200:
                data = response.json()
                return self._store_tokens(
                    data["access"], data.get("refresh", entry["refresh"])
                )["access"]
            self._invalidate_token()  # refresh rejected: fall through to a full login
        response = self._token_request(
            "", {"email": self.email, "password": self.password}
        )
        if response.status_code in (400, 401):
            raise WarehouseAuthError(
                "Warehouse rejected the service-account credentials"
            )
        if response.status_code >= 500:
            raise WarehouseUnavailable(
                f"auth endpoint returned HTTP {response.status_code}"
            )
        response.raise_for_status()
        data = response.json()
        logger.info("Logged in to the warehouse service as %s", self.email)
        return self._store_tokens(data["access"], data.get("refresh"))["access"]

    # ---------------------------------------------------------------- requests
    def _request(self, method, path, *, json_body=None, params=None, idempotent=True):
        url = f"{self.base_url}/{path.lstrip('/')}"
        attempts = self.max_attempts if idempotent else 1
        attempt, reauthed, last_error = 0, False, None
        while attempt < attempts:
            headers = {
                "Authorization": f"Bearer {self._access_token()}",
                REQUEST_ID_HEADER: get_request_id(),
            }
            started = time.monotonic()
            try:
                response = self.session.request(
                    method,
                    url,
                    json=json_body,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Warehouse %s %s failed (attempt %s/%s): %s",
                    method,
                    path,
                    attempt + 1,
                    attempts,
                    last_error,
                )
            else:
                logger.info(
                    "Warehouse %s %s -> %s in %.0f ms",
                    method,
                    path,
                    response.status_code,
                    (time.monotonic() - started) * 1000,
                )
                if response.status_code == 401 and not reauthed:
                    reauthed = (
                        True  # expired/revoked token: log in again once, not counted
                    )
                    self._invalidate_token()
                    continue
                if response.status_code in RETRYABLE_STATUS:
                    last_error = f"HTTP {response.status_code}"
                else:
                    return self._handle(response)
            attempt += 1
            if attempt < attempts:
                time.sleep(min(0.25 * 2 ** (attempt - 1), 2.0))
        raise WarehouseUnavailable(
            f"{method} {path} failed after {attempts} attempt(s): {last_error}"
        )

    def _handle(self, response):
        status = response.status_code
        try:
            data = response.json()
        except ValueError:
            data = {}
        if 200 <= status < 300:
            return data
        code = data.get("code") if isinstance(data, dict) else None
        if status == 409 and code == "insufficient_stock":
            raise InsufficientStock(data.get("shortages", []))
        if status == 409:
            raise ReservationConflict(data.get("detail", "conflict"))
        if status in (401, 403):
            raise WarehouseAuthError(
                f"Warehouse denied access (HTTP {status}): {data.get('detail', '')}"
            )
        if status in (400, 404):
            raise WarehouseBadRequest(
                f"Warehouse rejected the request (HTTP {status})", data
            )
        if status == 429 or status >= 500:
            raise WarehouseUnavailable(f"Warehouse error HTTP {status}")
        raise WarehouseError(f"Unexpected warehouse response HTTP {status}")

    # --------------------------------------------------------------- operations
    def reserve(self, order_id, items):
        """Reserve ``items`` (``[{"book_id", "quantity"}]``); idempotent per order."""
        return self._request(
            "POST", "reservations/", json_body={"order_id": order_id, "items": items}
        )

    def confirm(self, reservation_id):
        return self._request("POST", f"reservations/{reservation_id}/confirm/")

    def cancel(self, reservation_id):
        return self._request("POST", f"reservations/{reservation_id}/cancel/")

    def find_reservation(self, order_id):
        """Return the order's reservation or ``None`` (used if we lost the id)."""
        data = self._request("GET", "reservations/", params={"order_id": order_id})
        results = data.get("results", [])
        return results[0] if results else None

    def get_availability(self, book_ids):
        """``{book_id: {"available": int, "tracked": bool, ...}}`` per book."""
        data = self._request(
            "POST", "stock/availability/", json_body={"book_ids": list(book_ids)}
        )
        return {item["book_id"]: item for item in data["items"]}

    def restock(self, book_id, quantity, title="", isbn="", note=""):
        """Add stock. NOT idempotent, so never retried automatically."""
        return self._request(
            "POST",
            "stock/restock/",
            json_body={
                "book_id": book_id,
                "quantity": quantity,
                "title": title,
                "isbn": isbn,
                "note": note,
            },
            idempotent=False,
        )

    def health(self) -> bool:
        try:
            response = self.session.get(
                self.base_url.rsplit("/api", 1)[0] + "/health/", timeout=self.timeout
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
