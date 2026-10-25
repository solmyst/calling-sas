#!/usr/bin/env bash
set -euo pipefail
python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips='*'
