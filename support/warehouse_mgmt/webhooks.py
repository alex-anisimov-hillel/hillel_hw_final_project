"""HMAC-signed webhooks from the warehouse to ProjectA.

Signature = HMAC-SHA256(secret, f"{timestamp}.{raw_body}"), sent as
``X-Webhook-Signature: sha256=<hex>`` together with ``X-Webhook-Timestamp``.
ProjectA rejects bad signatures and timestamps older than a few minutes (replay).
"""

import hashlib
import hmac
import json
import logging
import time
import uuid

import requests
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from support.request_id import HEADER as REQUEST_ID_HEADER
from support.request_id import get_request_id

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
    """Temporary failure (network, 5xx, 429) - the Celery task retries it."""


def sign(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def deliver(event: str, data: dict, event_id: str | None = None) -> dict:
    url = settings.PROJECTA_WEBHOOK_URL
    secret = settings.WEBHOOK_SECRET
    if not url or not secret:
        logger.info(
            "Webhook %s skipped: PROJECTA_WEBHOOK_URL/WEBHOOK_SECRET not set", event
        )
        return {"status": "disabled"}

    payload = {
        "id": event_id or uuid.uuid4().hex,
        "event": event,
        "sent_at": timezone.now().isoformat(),
        "data": data,
    }
    body = json.dumps(
        payload, separators=(",", ":"), sort_keys=True, cls=DjangoJSONEncoder
    ).encode()
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature": sign(secret, timestamp, body),
        REQUEST_ID_HEADER: get_request_id(),
    }
    try:
        response = requests.post(
            url, data=body, headers=headers, timeout=settings.PROJECTA_WEBHOOK_TIMEOUT
        )
    except requests.RequestException as exc:
        logger.warning("Webhook %s to ProjectA failed: %s", event, exc)
        raise WebhookDeliveryError(str(exc)) from exc

    if response.status_code >= 500 or response.status_code in (408, 429):
        logger.warning(
            "Webhook %s got HTTP %s from ProjectA", event, response.status_code
        )
        raise WebhookDeliveryError(f"HTTP {response.status_code}")
    if response.status_code >= 400:
        # 4xx is permanent (bad signature, bad payload): retrying cannot help.
        logger.error(
            "Webhook %s rejected by ProjectA: HTTP %s", event, response.status_code
        )
        return {"status": "rejected", "http_status": response.status_code}
    logger.info("Webhook %s delivered (HTTP %s)", event, response.status_code)
    return {"status": "delivered", "http_status": response.status_code}
