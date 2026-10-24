"""
Production settings. Required variables fail fast at start-up instead of silently
falling back to an insecure default (same approach as ProjectA).
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import (
    ALLOWED_HOSTS,
    CSRF_TRUSTED_ORIGINS,
    DATABASES,
    LOGGING,
    env_bool,
    env_int,
    env_list,
    env_str,
)


def _required(name):
    value = env_str(name)
    if not value:
        raise ImproperlyConfigured(f"Environment variable {name} must be set")
    return value


DEBUG = False
SECRET_KEY = _required("DJANGO_SECRET_KEY")

_required("DJANGO_ALLOWED_HOSTS")
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain '*'")

# The service-to-service channel must not be silently disabled in production.
_required("WEBHOOK_SECRET")

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
# Internal ProjectA -> ProjectB calls travel over the private docker network
# (plain http), so the API and health check are exempt from the HTTPS redirect.
SECURE_REDIRECT_EXEMPT = env_list("DJANGO_SSL_REDIRECT_EXEMPT", r"^health/$,^api/")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

_required("CSRF_TRUSTED_ORIGINS")
if not all(origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must all use https://")

DATABASES["default"]["CONN_MAX_AGE"] = env_int("DB_CONN_MAX_AGE", 60)

LOGGING["root"] = {"handlers": ["console"], "level": "WARNING"}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
    },
}
