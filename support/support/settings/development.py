"""Development settings: DEBUG on, forgiving defaults."""

from .base import *  # noqa: F401,F403
from .base import env_bool, env_str

DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = env_str(
    "DJANGO_SECRET_KEY", "django-insecure-dev-only-key-do-not-use-in-production"
)
