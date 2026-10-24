"""Test settings: no external services needed (SQLite, locmem cache, eager Celery)."""

import os

from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK

DEBUG = False
SECRET_KEY = "test-secret-key-that-is-long-enough-for-hs256-signing"
ALLOWED_HOSTS = ["*"]

# SQLite by default; set POSTGRES_HOST (as CI does) to run on PostgreSQL, which also
# enables the row-locking concurrency tests.
if os.getenv("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("WAREHOUSE_POSTGRES_DB", "warehouse_db"),
            "USER": os.getenv("POSTGRES_USER", ""),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    }
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"anon": "10000/minute", "user": "10000/minute"},
}

PROJECTA_WEBHOOK_URL = "http://projecta.test/api/warehouse/webhook/"
WEBHOOK_SECRET = "test-webhook-secret"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
