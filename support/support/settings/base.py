"""
Base Django settings for the warehouse service (ProjectB), shared by every environment.

Environment-specific values live in ``development.py``, ``production.py``
and ``test.py``.
Everything secret or deployment-specific is read from environment variables
(optionally from a ``.env`` file in the project root, see ``.env.example``).
"""

import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env_str(name, default=""):
    return os.getenv(name, default)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default=0):
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


def env_list(name, default=""):
    return [i.strip() for i in os.getenv(name, default).split(",") if i.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:8001,http://127.0.0.1:8001"
)

# nginx terminates TLS and tells Django about it via X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "users.apps.UsersConfig",
    "warehouse_mgmt.apps.WarehouseMgmtConfig",
]

MIDDLEWARE = [
    "support.request_id.RequestIDMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "support.urls"
WSGI_APPLICATION = "support.wsgi.application"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_CREDENTIALS = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database / cache
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB"),
        "USER": env_str("POSTGRES_USER"),
        "PASSWORD": env_str("POSTGRES_PASSWORD"),
        "HOST": env_str("POSTGRES_HOST"),
        "PORT": env_str("POSTGRES_PORT", "5432"),
    }
}

REDIS_HOST = env_str("REDIS_HOST", "localhost")
# Logical Redis databases. ProjectA uses 0/1/2, so in the shared docker-compose
# stack this project gets 3 (broker) / 4 (cache) / 5 (results): no collisions.
REDIS_BROKER_DB = env_int("REDIS_BROKER_DB", 0)
REDIS_CACHE_DB = env_int("REDIS_CACHE_DB", 1)
REDIS_RESULT_DB = env_int("REDIS_RESULT_DB", 2)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379/{REDIS_CACHE_DB}",
    }
}

# ---------------------------------------------------------------------------
# Logging (every line carries the request id, see support/request_id.py)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "support.request_id.RequestIDFilter"},
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "standard",
        },
    },
    "loggers": {
        "warehouse_mgmt": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "users": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "support": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Auth / DRF / JWT
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "users.User"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "20/minute", "user": "600/minute"},
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "warehouse_mgmt.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 1)),
    "TOKEN_OBTAIN_SERIALIZER": "users.serializers.GroupsTokenObtainPairSerializer",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Warehouse service API",
    "DESCRIPTION": "Stock, reservations and movements for the book shop.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGES = [("en", _("English")), ("uk", _("Ukrainian"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Warehouse business settings
# ---------------------------------------------------------------------------
DEFAULT_WAREHOUSE_CODE = env_str("DEFAULT_WAREHOUSE_CODE", "main")
DEFAULT_LOW_STOCK_THRESHOLD = env_int("DEFAULT_LOW_STOCK_THRESHOLD", 10)
RESERVATION_TTL_MINUTES = env_int("RESERVATION_TTL_MINUTES", 30)
STOCK_CACHE_TTL = env_int("STOCK_CACHE_TTL", 60)  # seconds
REPORTS_DIR = BASE_DIR / "reports"

# ---------------------------------------------------------------------------
# Webhooks to ProjectA (HMAC-signed, see warehouse_mgmt/webhooks.py)
# ---------------------------------------------------------------------------
PROJECTA_WEBHOOK_URL = env_str("PROJECTA_WEBHOOK_URL")  # empty => webhooks disabled
WEBHOOK_SECRET = env_str("WEBHOOK_SECRET")
PROJECTA_WEBHOOK_TIMEOUT = (3.05, 10)  # (connect, read) seconds

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env_str(
    "CELERY_BROKER_URL", f"redis://{REDIS_HOST}:6379/{REDIS_BROKER_DB}"
)
CELERY_RESULT_BACKEND = env_str(
    "CELERY_RESULT_BACKEND", f"redis://{REDIS_HOST}:6379/{REDIS_RESULT_DB}"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 5 * 60
CELERY_RESULT_EXPIRES = 60 * 60 * 24
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CELERY_BEAT_SCHEDULE = {
    "expire-stale-reservations": {
        "task": "warehouse_mgmt.tasks.expire_stale_reservations",
        "schedule": 60.0,
    },
    "check-low-stock": {
        "task": "warehouse_mgmt.tasks.check_low_stock",
        "schedule": crontab(minute="*/30"),
    },
    "daily-stock-report": {
        "task": "warehouse_mgmt.tasks.generate_stock_report",
        "schedule": crontab(hour=2, minute=0),
    },
}
