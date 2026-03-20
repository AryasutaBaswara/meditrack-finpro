# MediTrack 🏥

> Drug & Prescription Management System — Final Project Backend Engineering

[![CI](https://github.com/your-username/meditrack/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/meditrack/actions/workflows/ci.yml)

---

## Overview

MediTrack is a backend-focused clinical drug inventory and prescription management system. It digitizes the full prescription lifecycle — from doctor-issued prescriptions through pharmacist dispensation — while enforcing strict data access control and providing AI-assisted drug safety checks.

**Key capabilities:**
- End-to-end prescription workflow with status tracking
- AI-powered drug interaction checker (OpenAI GPT-4o)
- Automated inventory management via database triggers
- Role-Based Access Control (RBAC) with Row-Level Security (RLS)
- Elasticsearch drug catalog search with fuzzy matching & autocomplete
- PDF prescription report generation

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.12) |
| Auth | Keycloak |
| Database | Supabase PostgreSQL |
| ORM + Migrations | SQLAlchemy Async + Alembic |
| Cache + Rate Limit | Redis |
| Search | Elasticsearch |
| AI | OpenAI GPT-4o |
| PDF | reportlab |
| Storage | Supabase Storage + Edge Functions |
| Reverse Proxy | NGINX |
| Container | Docker Compose (local) / Minikube (staging/prod) |
| CI/CD | GitHub Actions |
| E2E Automation | Playwright (TypeScript) |

---

## Project Structure

```
meditrack/
├── .github/
│   ├── workflows/          # CI/CD pipelines
│   └── copilot-instructions.md
├── services/
│   ├── fastapi/            # Core backend service
│   └── edge-functions/     # Supabase Edge Functions (Deno TS)
├── automation/             # Playwright E2E tests
├── infra/
│   ├── docker/             # Docker Compose (local dev)
│   ├── k8s/                # Kubernetes manifests (staging/prod)
│   └── supabase/           # Migrations + seed scripts
├── docs/                   # Architecture blueprint
├── .env.example
├── Makefile
└── README.md
```

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 18+
- `make`

### Local Development

```bash
# 1. Clone the repository
git clone https://github.com/your-username/meditrack.git
cd meditrack

# 2. First-time setup
make setup

# 3. Fill in your credentials
vim .env

# 4. Start all services
make dev

# 5. Run migrations & seed
make migrate
make seed
```

API docs available at: `http://localhost:8000/docs`

---

## Available Commands

```bash
make help        # Show all available commands
make dev         # Start local development environment
make test        # Run all tests
make lint        # Run linter
make migrate     # Run database migrations
make seed        # Seed database with sample data
make k8s-up      # Deploy to Minikube
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

See `.env.example` for all required variables with descriptions.

---

## API Documentation

Once running, interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Testing

```bash
make test-unit    # Unit tests (pytest)
make test-int     # Integration tests (pytest + httpx)
make test-e2e     # E2E automation (Playwright)
make test-load    # Load tests — 100 concurrent users (k6)
make test-cov     # Tests with coverage report
```

---

## Architecture

See [`docs/MediTrack_Blueprint.docx`](docs/MediTrack_Blueprint.docx) for the full architecture blueprint including:
- System architecture diagram
- Database schema (14 tables)
- RBAC roles & permissions
- API design overview
- CI/CD pipeline design
- Development roadmap

---

## RBAC Roles

| Role | Permissions |
|---|---|
| `admin` | Full system access |
| `doctor` | Create prescriptions, view patients, trigger AI check |
| `pharmacist` | Process dispensations, manage drug stock |
| `patient` | View own prescriptions only (RLS enforced) |

---

## License

This project is developed as a final project for Backend Engineering coursework.
