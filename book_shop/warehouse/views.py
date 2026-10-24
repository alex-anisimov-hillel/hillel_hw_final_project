"""Webhook receiver for events pushed by the warehouse service."""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from warehouse.signature import InvalidSignature, verify
from warehouse.tasks import apply_stock_levels

logger = logging.getLogger(__name__)

EVENT_CACHE_SECONDS = 15 * 60


class SignedWebhookView(APIView):
    """Base class: verifies the HMAC signature + timestamp, de-duplicates by event id,
    then dispatches to ``handle_<event with dots as underscores>``."""

    authentication_classes = []  # machine-to-machine, authenticated by signature
    permission_classes = [AllowAny]
    throttle_classes = []
    secret_setting = None

    def get_secret(self):
        return getattr(settings, self.secret_setting, "")

    def post(self, request):
        secret = self.get_secret()
        if not secret:
            logger.error(
                "Webhook received but %s is not configured", self.secret_setting
            )
            return Response(
                {"detail": "webhook not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        body = request.body  # raw bytes: must be read before DRF parses the stream
        try:
            verify(
                secret,
                request.headers.get("X-Webhook-Timestamp", ""),
                request.headers.get("X-Webhook-Signature", ""),
                body,
                settings.WAREHOUSE_WEBHOOK_TOLERANCE,
            )
        except InvalidSignature as exc:
            logger.warning("Rejected webhook: %s", exc)
            return Response(
                {"detail": "invalid signature"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            payload = json.loads(body)
            event, event_id, data = payload["event"], payload["id"], payload["data"]
        except (ValueError, KeyError, TypeError):
            return Response(
                {"detail": "malformed payload"}, status=status.HTTP_400_BAD_REQUEST
            )

        cache_key = f"webhook:event:{event_id}"
        if cache.get(cache_key):
            logger.info("Webhook %s (%s) already processed", event, event_id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        handler = getattr(self, "handle_" + event.replace(".", "_"), None)
        if handler is None:
            logger.info("Ignoring unknown webhook event %s", event)
            return Response({"detail": "ignored"}, status=status.HTTP_202_ACCEPTED)
        handler(data)
        cache.set(
            cache_key, 1, EVENT_CACHE_SECONDS
        )  # only after success => failures are retried
        return Response(status=status.HTTP_204_NO_CONTENT)


class WarehouseWebhookView(SignedWebhookView):
    secret_setting = "WAREHOUSE_WEBHOOK_SECRET"

    def handle_stock_changed(self, data):
        levels = {int(i["book_id"]): int(i["available"]) for i in data.get("items", [])}
        changed = apply_stock_levels(levels)
        logger.info(
            "stock.changed: %s book(s) received, %s updated", len(levels), changed
        )

    def handle_stock_low(self, data):
        items = data.get("items", [])
        lines = [
            f"#{i['book_id']} {i.get('title', '')}: {i['available']} left"
            for i in items
        ]
        logger.warning("stock.low: %s item(s) below threshold", len(items))
        if settings.LOW_STOCK_ALERT_EMAILS and lines:
            send_mail(
                subject="Low stock alert",
                message="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=settings.LOW_STOCK_ALERT_EMAILS,
                fail_silently=True,
            )
