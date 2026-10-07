#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy from .env.example and set ADMIN_PASSWORD / SECRET_KEY."
  exit 1
fi

exec docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build "$@"
