"""
Production settings.

Everything deployment-specific comes from environment variables (see
``.env.example``). Required variables fail fast at start-up instead of
silently falling back to an insecure default.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import (
    ALLOWED_HOSTS,
    CSRF_TRUSTED_ORIGINS,
    DATABASES,
    EMAIL_BACKEND,
    LOGGING,
    env_bool,
    env_int,
    env_str,
)


def _required(name):
    value = env_str(name)
    if not value:
        raise ImproperlyConfigured(f"Environment variable {name} must be set")
    return value


DEBUG = False

SECRET_KEY = _required("DJANGO_SECRET_KEY")

# Real hosts only: no localhost fallback, no wildcard.
_required("DJANGO_ALLOWED_HOSTS")
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain '*'")

# ---------------------------------------------------------------------------
# HTTPS / security headers
# ---------------------------------------------------------------------------
# Redirect all plain-HTTP requests to HTTPS (nginx must forward
# X-Forwarded-Proto, see SECURE_PROXY_SSL_HEADER in base.py). Set
# DJANGO_SECURE_SSL_REDIRECT=False only for an internal health-check setup
# without TLS.
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)

# The warehouse service posts webhooks over the private docker network (plain http).
# Only this path is exempt; HMAC signature + timestamp protect it.
SECURE_REDIRECT_EXEMPT = [r"^api/warehouse/webhook/$"]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# HSTS: start low when first enabling (e.g. DJANGO_SECURE_HSTS_SECONDS=3600),
# then raise to a year once HTTPS is confirmed working everywhere.
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Trusted origins must be set explicitly (no localhost defaults) and be https.
_required("CSRF_TRUSTED_ORIGINS")
if not all(origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must all use https://")

# ---------------------------------------------------------------------------
# Other production hardening
# ---------------------------------------------------------------------------
# Keep DB connections open between requests.
DATABASES["default"]["CONN_MAX_AGE"] = env_int("DB_CONN_MAX_AGE", 60)

# No e-mail credentials in code; fail if SMTP is selected but not configured.
if EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    _required("EMAIL_HOST_USER")
    _required("EMAIL_HOST_PASSWORD")

# CORS: explicit allow-list from the environment only.
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in env_str("CORS_ALLOWED_ORIGINS").split(",") if o.strip()
]

# Log warnings and errors from everything (not just "books") to the console so
# `docker logs` shows them; Django's own request errors are included.
LOGGING["root"] = {"handlers": ["console"], "level": "WARNING"}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
    },
}
