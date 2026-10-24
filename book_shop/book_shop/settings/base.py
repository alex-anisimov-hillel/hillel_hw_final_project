"""
Base Django settings for book_shop, shared by every environment.

Environment-specific values live in ``development.py`` / ``production.py``.
Anything secret or deployment-specific is read from environment variables
(optionally loaded from a ``.env`` file in the project root, see
``.env.example``).
"""

import os
from pathlib import Path

import sentry_sdk
from celery.schedules import crontab
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# <project root>/book_shop/settings/base.py -> parents[2] is <project root>
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Real environment variables always win over values from the .env file.
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
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
# SECRET_KEY and DEBUG are set per environment (development.py / production.py).
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", "http://localhost,http://127.0.0.1"
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
    "books.apps.BooksConfig",
    "categories.apps.CategoriesConfig",
    "users.apps.UsersConfig",
    "orders.apps.OrdersConfig",
    "payment.apps.PaymentConfig",
    "django_filters",
    "mptt",
    "drf_spectacular",
    "corsheaders",
    "warehouse.apps.WarehouseConfig",
]

MIDDLEWARE = [
    "warehouse.request_id.RequestIDMiddleware",
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

ROOT_URLCONF = "book_shop.urls"

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:5173,http://127.0.0.1:5173",
)
CORS_ALLOW_CREDENTIALS = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "users" / "templates" / "registration",
            BASE_DIR / "book_shop" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "book_shop.wsgi.application"

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
        "PORT": env_str("POSTGRES_PORT"),
    }
}

REDIS_HOST = env_str("REDIS_HOST", "localhost")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379/1",  # /1 targets Redis db index 1
    }
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "warehouse.request_id.RequestIDFilter"},
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
        "books": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "warehouse": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "orders": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Auth / DRF
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "users.User"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10/minute",
    },
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGES = [
    ("en", _("English")),
    ("uk", _("Ukrainian")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ---------------------------------------------------------------------------
# Business settings: cart, Stripe, e-mail
# ---------------------------------------------------------------------------
CART_SESSION_ID = "cart"

STRIPE_SECRET_KEY = env_str("STRIPE_SECRET_KEY")
STRIPE_PUBLIC_KEY = env_str("STRIPE_PUBLIC_KEY")

EMAIL_BACKEND = env_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env_str("EMAIL_HOST", "sandbox.smtp.mailtrap.io")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "webmaster@localhost")

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", f"redis://{REDIS_HOST}:6379/0")
CELERY_RESULT_BACKEND = env_str(
    "CELERY_RESULT_BACKEND", f"redis://{REDIS_HOST}:6379/2"
)  # /1 is the cache
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 5 * 60
CELERY_RESULT_EXPIRES = 60 * 60 * 24
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

REPORTS_DIR = BASE_DIR / "reports"

# ---------------------------------------------------------------------------
# Warehouse service (ProjectB) integration
# ---------------------------------------------------------------------------
# Off by default: the shop works standalone (and its tests need no second service).
WAREHOUSE_ENABLED = env_bool("WAREHOUSE_ENABLED", False)
WAREHOUSE_API_URL = env_str("WAREHOUSE_API_URL", "http://warehouse-api/api")
WAREHOUSE_SERVICE_EMAIL = env_str("WAREHOUSE_SERVICE_EMAIL")
WAREHOUSE_SERVICE_PASSWORD = env_str("WAREHOUSE_SERVICE_PASSWORD")
# Shared with ProjectB's WEBHOOK_SECRET; signs webhooks B -> A.
WAREHOUSE_WEBHOOK_SECRET = env_str("WAREHOUSE_WEBHOOK_SECRET")
WAREHOUSE_WEBHOOK_TOLERANCE = env_int("WAREHOUSE_WEBHOOK_TOLERANCE", 300)  # seconds
WAREHOUSE_TIMEOUT = (
    2.05,
    5,
)  # (connect, read) seconds - kept short, web requests wait on it
WAREHOUSE_MAX_ATTEMPTS = env_int("WAREHOUSE_MAX_ATTEMPTS", 2)
LOW_STOCK_ALERT_EMAILS = env_list("LOW_STOCK_ALERT_EMAILS", "")

CELERY_BEAT_SCHEDULE = {
    "generate-sales-report": {
        "task": "orders.tasks.generate_sales_report",
        "schedule": crontab(hour=14, minute=15),
    },
    "cleanup-expired-sessions": {
        "task": "users.tasks.cleanup_expired_sessions",
        "schedule": crontab(hour=14, minute=15),
    },
    "warehouse-sync-stock": {
        "task": "warehouse.tasks.sync_stock_levels",
        "schedule": crontab(minute="*/10"),
    },
    "warehouse-retry-pending-reservations": {
        "task": "warehouse.tasks.retry_pending_reservations",
        "schedule": crontab(minute="*/5"),
    },
}

# ---------------------------------------------------------------------------
# Sentry error monitoring (enabled only when SENTRY_DSN is set)
# ---------------------------------------------------------------------------
SENTRY_DSN = env_str("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env_str("SENTRY_ENVIRONMENT", "development"),
        traces_sample_rate=float(env_str("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )  # Django and Celery integrations are enabled automatically
