#!/bin/sh
set -eu

if [ "${1:-}" = "gunicorn" ]; then
    python manage.py migrate --noinput
    python manage.py bootstrap_organizer
    unset OLYMPICS_ORGANIZER_USERNAME OLYMPICS_ORGANIZER_PASSWORD
fi

exec "$@"
