#!/bin/sh
set -e

# The schema comes first, because a table the image expects and the database does not have is every read of it failing.
echo "[fastkit] applying the schema of ${APP_ENV}"
python manage.py migrate

# Which peers may speak for a client is a property of this deployment, so it is read from the very configuration the process loads.
TRUSTED_PROXIES=$(python -c "from helpers.settings import settings; print(settings.trusted_proxies)")

echo "[fastkit] serving on 0.0.0.0:${PORT} behind ${TRUSTED_PROXIES}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips "${TRUSTED_PROXIES}"
