import os

from celery import Celery
from celery.signals import task_postrun, task_prerun

from support.request_id import request_id_var

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "support.settings.development")

app = Celery("support")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

_tokens = {}


@task_prerun.connect
def _bind_request_id(task_id=None, **kwargs):
    _tokens[task_id] = request_id_var.set(f"task-{task_id[:8]}")


@task_postrun.connect
def _unbind_request_id(task_id=None, **kwargs):
    token = _tokens.pop(task_id, None)
    if token is not None:
        request_id_var.reset(token)
