.PHONY: dev-up dev-down dev-logs dev-shell prod-up compose-config

COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_PROD = docker compose -f docker-compose.yml $(if $(wildcard docker-compose.prod.yml),-f docker-compose.prod.yml,)

dev-up:
	$(COMPOSE_DEV) up --build

dev-down:
	$(COMPOSE_DEV) down

dev-logs:
	$(COMPOSE_DEV) logs -f web

dev-shell:
	$(COMPOSE_DEV) exec web sh

prod-up:
	$(COMPOSE_PROD) up -d --build

compose-config:
	$(COMPOSE_DEV) config
