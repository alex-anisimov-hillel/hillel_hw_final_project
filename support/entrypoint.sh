#!/bin/sh
# Only the web container runs migrations/collectstatic (RUN_MIGRATIONS=1); workers just wait for it.
set -e

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  python manage.py bootstrap_service_account
fi

exec "$@"
