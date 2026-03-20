# ─────────────────────────────────────────────────────────────
# MediTrack — Makefile
# Usage: make <target>
# ─────────────────────────────────────────────────────────────

.PHONY: help dev down restart logs build test test-unit test-integration \
        test-e2e lint format migrate seed k8s-up k8s-down k8s-status \
        k8s-logs clean setup

# ── Default ───────────────────────────────────────────────────
help:
	@echo ""
	@echo "  MediTrack — Available Commands"
	@echo "  ─────────────────────────────────────────────"
	@echo "  Dev Environment:"
	@echo "    make setup          First-time setup (install deps)"
	@echo "    make dev            Start all services (Docker Compose)"
	@echo "    make down           Stop all services"
	@echo "    make restart        Restart all services"
	@echo "    make logs           Tail logs from all services"
	@echo "    make build          Rebuild Docker images"
	@echo ""
	@echo "  Database:"
	@echo "    make migrate        Run Alembic migrations"
	@echo "    make migrate-down   Rollback last migration"
	@echo "    make seed           Run database seed script"
	@echo "    make migration m=   Create new migration (make migration m='add_users')"
	@echo ""
	@echo "  Testing:"
	@echo "    make test           Run all tests"
	@echo "    make test-unit      Run unit tests only"
	@echo "    make test-int       Run integration tests only"
	@echo "    make test-e2e       Run Playwright E2E tests"
	@echo "    make test-load      Run k6 load tests"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint           Run ruff linter"
	@echo "    make format         Run black formatter"
	@echo "    make check          Run lint + format check (CI mode)"
	@echo ""
	@echo "  Kubernetes (Staging/Prod):"
	@echo "    make k8s-up         Apply all K8s manifests to minikube"
	@echo "    make k8s-down       Delete all K8s resources"
	@echo "    make k8s-status     Show all pods status"
	@echo "    make k8s-logs       Tail FastAPI pod logs"
	@echo ""
	@echo "  Misc:"
	@echo "    make clean          Remove all containers, volumes, caches"
	@echo "  ─────────────────────────────────────────────"
	@echo ""

# ── First-time Setup ──────────────────────────────────────────
setup:
	@echo "→ Copying .env.example to .env..."
	@cp -n .env.example .env || echo "  .env already exists, skipping."
	@echo "→ Installing FastAPI dependencies..."
	@cd services/fastapi && pip install -r requirements.txt
	@echo "→ Installing Playwright dependencies..."
	@cd automation && npm install
	@npx playwright install
	@echo "✅ Setup complete. Edit .env with your credentials."

# ── Docker Compose (Local Dev) ────────────────────────────────
dev:
	@echo "→ Starting MediTrack services..."
	docker compose -f infra/docker/docker-compose.yml up -d
	@echo "✅ Services running. FastAPI: http://localhost:8000/docs"

down:
	docker compose -f infra/docker/docker-compose.yml down

restart:
	docker compose -f infra/docker/docker-compose.yml restart

logs:
	docker compose -f infra/docker/docker-compose.yml logs -f

logs-api:
	docker compose -f infra/docker/docker-compose.yml logs -f fastapi

build:
	docker compose -f infra/docker/docker-compose.yml build --no-cache

# ── Database Migrations ───────────────────────────────────────
migrate:
	@echo "→ Running Alembic migrations..."
	cd services/fastapi && alembic upgrade head

migrate-down:
	@echo "→ Rolling back last migration..."
	cd services/fastapi && alembic downgrade -1

migration:
	@[ -n "$(m)" ] || (echo "❌ Usage: make migration m='your_migration_name'" && exit 1)
	@echo "→ Creating migration: $(m)"
	cd services/fastapi && alembic revision --autogenerate -m "$(m)"

seed:
	@echo "→ Running seed script..."
	cd services/fastapi && python -m app.db.seed

# ── Testing ───────────────────────────────────────────────────
test:
	@echo "→ Running all tests..."
	@make test-unit
	@make test-int
	@make test-e2e

test-unit:
	@echo "→ Running unit tests..."
	cd services/fastapi && pytest tests/unit -v --tb=short

test-int:
	@echo "→ Running integration tests..."
	cd services/fastapi && pytest tests/integration -v --tb=short

test-e2e:
	@echo "→ Running Playwright E2E tests..."
	cd automation && npx playwright test

test-load:
	@echo "→ Running k6 load tests..."
	k6 run automation/load/load_test.js

test-cov:
	@echo "→ Running tests with coverage..."
	cd services/fastapi && pytest tests/ --cov=app --cov-report=html --cov-report=term

# ── Code Quality ──────────────────────────────────────────────
lint:
	@echo "→ Running ruff..."
	cd services/fastapi && ruff check app/ tests/

format:
	@echo "→ Running black..."
	cd services/fastapi && black app/ tests/

check:
	@echo "→ Running CI checks (lint + format check)..."
	cd services/fastapi && ruff check app/ tests/
	cd services/fastapi && black --check app/ tests/

# ── Kubernetes (Staging / Prod) ───────────────────────────────
k8s-up:
	@echo "→ Applying K8s manifests to minikube..."
	kubectl apply -f infra/k8s/keycloak/
	kubectl apply -f infra/k8s/redis/
	kubectl apply -f infra/k8s/elasticsearch/
	kubectl apply -f infra/k8s/fastapi/
	kubectl apply -f infra/k8s/nginx/
	@echo "✅ All manifests applied."

k8s-down:
	@echo "→ Deleting K8s resources..."
	kubectl delete -f infra/k8s/ --ignore-not-found=true

k8s-status:
	kubectl get pods -A

k8s-logs:
	kubectl logs -l app=meditrack-fastapi -f

k8s-restart:
	kubectl rollout restart deployment/meditrack-fastapi

# ── Elasticsearch ─────────────────────────────────────────────
es-index:
	@echo "→ Creating/updating Elasticsearch drug index..."
	cd services/fastapi && python -m app.services.search_indexer

# ── Cleanup ───────────────────────────────────────────────────
clean:
	@echo "→ Stopping and removing containers, volumes, networks..."
	docker compose -f infra/docker/docker-compose.yml down -v --remove-orphans
	@echo "→ Removing Python caches..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned."
