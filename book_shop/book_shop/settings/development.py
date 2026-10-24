"""Development settings: DEBUG on, debug toolbar, forgiving defaults."""

from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE, env_bool, env_str

DEBUG = env_bool("DJANGO_DEBUG", True)

# Insecure on purpose - only ever used for local development.
SECRET_KEY = env_str(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-key-do-not-use-in-production",
)

INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]
MIDDLEWARE = [*MIDDLEWARE, "debug_toolbar.middleware.DebugToolbarMiddleware"]
INTERNAL_IPS = ["127.0.0.1"]

# Print e-mails to the console unless an SMTP backend is requested explicitly.
EMAIL_BACKEND = env_str(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
