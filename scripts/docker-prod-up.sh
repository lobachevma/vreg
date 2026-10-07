#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy from .env.example and set ADMIN_PASSWORD / SECRET_KEY."
  exit 1
fi

COMPOSE_FILES=(-f docker-compose.yml)
if [[ -f docker-compose.prod.yml ]]; then
  COMPOSE_FILES+=(-f docker-compose.prod.yml)
elif [[ -f docker-compose.prod.example.yml ]]; then
  echo "Tip: copy docker-compose.prod.example.yml to docker-compose.prod.yml for production port binding."
fi

exec docker compose "${COMPOSE_FILES[@]}" up -d --build "$@"
