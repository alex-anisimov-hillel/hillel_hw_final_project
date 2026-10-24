import logging

from celery import shared_task
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_sessions():
    expired = Session.objects.filter(expire_date__lt=timezone.now()).count()
    call_command("clearsessions")
    logger.info("Expired sessions removed: %s", expired)
    return {"expired_sessions_removed": expired}
