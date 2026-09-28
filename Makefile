-include .env
PY ?= .venv/bin/python
COMPOSE ?= docker compose
API_PORT ?= 8000
export DOCKER_UID := $(shell id -u)
export DOCKER_GID := $(shell id -g)

.PHONY: dev up seed jobs metrics migrate wait test demo logs worker-logs down reset psql redis-cli

dev: up wait seed jobs   ## bring up postgres+redis+api+worker+cron, migrate, seed, run all jobs once
	@echo "API: http://localhost:$(API_PORT)/docs"

up:
	$(COMPOSE) up -d --build

wait:
	@echo -n "waiting for api"; for i in $$(seq 1 60); do \
	  curl -fsS http://localhost:$(API_PORT)/health >/dev/null 2>&1 && echo " ok" && exit 0; echo -n "."; sleep 2; done; \
	  echo " timeout"; $(COMPOSE) logs api | tail -30; exit 1

seed:
	$(COMPOSE) exec api python -m api.seed

jobs:                     ## run fold + cohorts + today's metrics now (cron does this on schedule)
	$(COMPOSE) exec api python -m worker.jobs all --day today

metrics:                  ## DAY=2026-09-27 make metrics   (default: yesterday)
	$(COMPOSE) exec api python -m worker.jobs metrics --day $(or $(DAY),yesterday)

migrate:
	$(COMPOSE) exec api alembic upgrade head

test:
	$(PY) -m pytest

demo:
	$(PY) -m engine.demo

logs:
	$(COMPOSE) logs -f api

worker-logs:
	$(COMPOSE) logs -f worker cron

down:
	$(COMPOSE) down

reset:                    ## wipe DB + Redis + media and start over
	$(COMPOSE) down -v
	$(COMPOSE) run --rm --no-deps --user root api sh -c 'rm -rf /app/media/*'
	$(MAKE) dev

psql:
	$(COMPOSE) exec postgres psql -U vibo -d vibo

redis-cli:
	$(COMPOSE) exec redis redis-cli
