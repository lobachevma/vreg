# Docker workflow for VReg

Краткая инструкция по работе с проектом в Docker (разработка и production).

## Prerequisites

- Docker Engine + Docker Compose v2
- Файл `.env` (скопируйте из `.env.example`, задайте `ADMIN_PASSWORD` и `SECRET_KEY`)

## Production-style run (Gunicorn)

```bash
docker compose up -d --build
```

- URL: http://localhost:8000 (если не меняли `WEB_PUBLISH`)
- Остановка: `docker compose down` (данные PostgreSQL в volume `postgres_data`)

## Development (hot reload)

```bash
./scripts/docker-dev-up.sh
```

Эквивалент: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`

| Task | Command |
|------|---------|
| Stop | `./scripts/docker-dev-down.sh` or `make dev-down` |
| Logs | `make dev-logs` |
| Shell | `./scripts/docker-dev-shell.sh` |
| Validate compose | `make compose-config` |

## Production on a specific host IP

1. `cp docker-compose.prod.example.yml docker-compose.prod.yml`
2. Отредактируйте `ports`
3. `./scripts/docker-prod-up.sh`

## Dev Container (Cursor / VS Code)

**Reopen in Container** — использует `docker-compose.yml` + `docker-compose.dev.yml`, workspace `/app`, порт `8000`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `ADMIN_PASSWORD` | Пароль `admin` |
| `SECRET_KEY` | Flask session secret |
| `WEB_PUBLISH` | `hostPort:8000` (default `8000:8000`) |

See also Project Context copy at the same path under agent store if you use Cursor Projects.
