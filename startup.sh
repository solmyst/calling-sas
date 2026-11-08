#!/usr/bin/env bash
# Azure App Service entry point. It binds publicly, so it must never run in
# local mode: hosted mode refuses to start without a password, secret and HTTPS origin.
set -euo pipefail
export APP_ENV="${APP_ENV:-production}"
if [ "$APP_ENV" = "local" ]; then
  echo "startup.sh binds 0.0.0.0; set APP_ENV=production with DEMO_PASSWORD and SESSION_SECRET." >&2
  exit 1
fi
# Proxy headers are trusted only from loopback (uvicorn default), so clients
# cannot choose their own IP for the login rate limit with X-Forwarded-For.
python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
