"""Celery tasks for the payment app."""

import logging
from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_order_confirmation_email_task(email, order_id):
    if not email:
        return "skipped: no email address"

    sent = send_mail(
        subject="Order confirmation",
        message=f"The payment for your order #{order_id} was successful!",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    logger.info("Confirmation email for order %s sent to %s", order_id, email)
    return sent
