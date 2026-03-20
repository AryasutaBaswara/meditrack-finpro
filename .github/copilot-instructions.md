# MediTrack — GitHub Copilot Instructions

> This file is the source of truth for GitHub Copilot when working on this project.
> Read this entire file before generating any code.

---

## Project Overview

MediTrack is a **backend-only** Drug & Prescription Management System.
- Final project — Backend Engineering
- Solo developer
- API-first, no frontend in scope
- Domain: Medical / Clinical (drugs, prescriptions, dispensations)

---

## Absolute Rules — Never Violate These

```
1. NEVER use sync SQLAlchemy — always async
2. NEVER hardcode credentials — always use settings.py
3. NEVER return raw dict from endpoints — always use response envelope
4. NEVER use Flask or Django patterns
5. NEVER create a new file without __init__.py in its package
6. NEVER write a route handler with business logic inside it
   → routes call services, services call db
7. NEVER use print() for logging — always use Python logging module
8. NEVER catch bare Exception without re-raising or logging
9. NEVER skip Pydantic validation on request bodies
10. NEVER commit secrets, .env files, or API keys
```

---

## Tech Stack — Do Not Deviate

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Framework | FastAPI | latest stable |
| ORM | SQLAlchemy | async, 2.x |
| Migrations | Alembic | latest stable |
| Validation | Pydantic | v2 |
| Auth | Keycloak JWT | via python-jose |
| Cache | Redis | via redis-py async |
| Search | Elasticsearch | via elasticsearch-py async, 8.x |
| AI | OpenAI GPT-4o | via openai SDK |
| PDF | reportlab | latest stable |
| Storage | Supabase Storage | via supabase-py |
| Testing | pytest + pytest-asyncio | latest stable |
| HTTP client (tests) | httpx | latest stable |
| Linter | ruff | latest stable |
| Formatter | black | latest stable |

---

## Project Structure

```
meditrack/
├── .github/
│   ├── workflows/
│   │   └── ci.yml
│   └── copilot-instructions.md       ← YOU ARE HERE
├── services/
│   ├── fastapi/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   └── v1/
│   │   │   │       ├── routes/       ← route handlers only, no business logic
│   │   │   │       │   ├── drugs.py
│   │   │   │       │   ├── prescriptions.py
│   │   │   │       │   ├── patients.py
│   │   │   │       │   ├── dispensations.py
│   │   │   │       │   ├── auth.py
│   │   │   │       │   ├── ai.py
│   │   │   │       │   ├── storage.py
│   │   │   │       │   └── reports.py
│   │   │   │       └── dependencies.py   ← FastAPI Depends()
│   │   │   ├── core/
│   │   │   │   ├── config.py         ← all env vars via pydantic BaseSettings
│   │   │   │   ├── security.py       ← JWT validation, RBAC
│   │   │   │   ├── exceptions.py     ← custom exception classes
│   │   │   │   └── responses.py      ← response envelope helpers
│   │   │   ├── models/               ← Pydantic request/response schemas
│   │   │   │   ├── drug.py
│   │   │   │   ├── prescription.py
│   │   │   │   ├── patient.py
│   │   │   │   └── common.py         ← shared models (pagination, etc)
│   │   │   ├── services/             ← all business logic lives here
│   │   │   │   ├── drug_service.py
│   │   │   │   ├── prescription_service.py
│   │   │   │   ├── patient_service.py
│   │   │   │   ├── dispensation_service.py
│   │   │   │   ├── ai_service.py     ← OpenAI integration
│   │   │   │   ├── search_service.py ← Elasticsearch integration
│   │   │   │   ├── cache_service.py  ← Redis integration
│   │   │   │   ├── pdf_service.py    ← reportlab PDF generation
│   │   │   │   └── storage_service.py ← Supabase Storage
│   │   │   ├── db/
│   │   │   │   ├── session.py        ← SQLAlchemy async engine + session
│   │   │   │   ├── base.py           ← declarative base
│   │   │   │   ├── models/           ← SQLAlchemy ORM models (14 tables)
│   │   │   │   │   ├── user.py
│   │   │   │   │   ├── drug.py
│   │   │   │   │   ├── prescription.py
│   │   │   │   │   └── ...
│   │   │   │   └── seed.py           ← database seeding script
│   │   │   └── main.py               ← FastAPI app entrypoint
│   │   ├── tests/
│   │   │   ├── unit/                 ← test services in isolation (mock db)
│   │   │   └── integration/          ← test endpoints with real db
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── alembic.ini
│   └── edge-functions/
│       ├── storage-handler/index.ts  ← Supabase Storage ops
│       └── stock-webhook/index.ts    ← DB webhook → stock alert
├── automation/                       ← Playwright E2E (TypeScript)
├── infra/
│   ├── docker/docker-compose.yml
│   ├── k8s/                          ← Kubernetes manifests
│   └── supabase/
│       ├── migrations/               ← Alembic + raw SQL migrations
│       └── seed/seed.sql
└── Makefile
```

---

## Service Port Map (Docker Compose — Local Dev)

| Service | Internal Host | Port |
|---|---|---|
| FastAPI | `fastapi` | `8000` |
| NGINX | `nginx` | `80` |
| Keycloak | `keycloak` | `8080` |
| PostgreSQL | `postgres` | `5432` |
| Redis | `redis` | `6379` |
| Elasticsearch | `elasticsearch` | `9200` |

---

## Coding Patterns — Always Follow These

### 1. Layered Architecture (strict)

```
Request → Route Handler → Service → DB / External API → Response

# Route handler: ONLY handle HTTP concerns
@router.post("/prescriptions", response_model=ApiResponse[PrescriptionResponse])
async def create_prescription(
    body: PrescriptionCreate,
    current_user: TokenData = Depends(get_current_user),
    service: PrescriptionService = Depends(get_prescription_service),
):
    result = await service.create(body, current_user)
    return success_response(data=result)

# Service: ALL business logic
class PrescriptionService:
    async def create(self, body: PrescriptionCreate, user: TokenData):
        # validate, call AI, call DB, etc.
        ...
```

### 2. API Response Envelope — Always Use This

```python
# core/responses.py defines these helpers

# Success response
def success_response(data=None, message=None, meta=None):
    return {"data": data, "error": None, "meta": meta}

# Error response
def error_response(code: str, message: str):
    return {"data": None, "error": {"code": code, "message": message}, "meta": None}

# Paginated response
def paginated_response(data, total, page, per_page):
    return {
        "data": data,
        "error": None,
        "meta": {"total": total, "page": page, "per_page": per_page}
    }

# CORRECT usage:
return success_response(data=drug)
return error_response(code="DRUG_NOT_FOUND", message="Drug with id 99 not found")
return paginated_response(data=drugs, total=150, page=1, per_page=20)

# WRONG — never do this:
return {"id": 1, "name": "Amoxicillin"}       # no envelope
return {"success": True, "data": drug}         # wrong format
```

### 3. Settings — Always via Pydantic BaseSettings

```python
# core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    redis_url: str
    elasticsearch_url: str
    keycloak_url: str
    keycloak_realm: str
    keycloak_jwks_url: str
    openai_api_key: str
    openai_model: str = "gpt-4o"
    supabase_url: str
    supabase_service_role_key: str

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()

# Usage — always import settings, never os.getenv() directly:
from app.core.config import settings
url = settings.database_url       # CORRECT
url = os.getenv("DATABASE_URL")   # WRONG
```

### 4. SQLAlchemy Async — Always This Pattern

```python
# db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine(settings.database_url, echo=False, pool_size=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# Usage in service:
class DrugService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, drug_id: int):
        result = await self.db.execute(
            select(Drug).where(Drug.id == drug_id)
        )
        return result.scalar_one_or_none()
```

### 5. JWT Validation + RBAC

```python
# core/security.py
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

bearer_scheme = HTTPBearer()

async def get_current_user(token=Depends(bearer_scheme)) -> TokenData:
    # Validate Keycloak JWT via JWKS
    # Extract sub, email, realm_access.roles
    ...

def require_roles(*roles: str):
    async def role_checker(current_user: TokenData = Depends(get_current_user)):
        if not any(role in current_user.roles for role in roles):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker

# Usage in routes:
@router.post("/prescriptions")
async def create_prescription(
    current_user: TokenData = Depends(require_roles("doctor", "admin")),
):
    ...
```

### 6. Error Handling — Always Structured

```python
# core/exceptions.py
class MediTrackException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

class DrugNotFoundException(MediTrackException):
    def __init__(self, drug_id: int):
        super().__init__(
            code="DRUG_NOT_FOUND",
            message=f"Drug with id {drug_id} does not exist",
            status_code=404
        )

class InsufficientStockException(MediTrackException):
    def __init__(self, drug_name: str):
        super().__init__(
            code="INSUFFICIENT_STOCK",
            message=f"Insufficient stock for drug: {drug_name}",
            status_code=422
        )

# In main.py — register exception handler:
@app.exception_handler(MediTrackException)
async def meditrack_exception_handler(request, exc: MediTrackException):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code=exc.code, message=exc.message)
    )
```

### 7. Redis Caching Pattern

```python
# services/cache_service.py
import redis.asyncio as redis
import json

class CacheService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def get(self, key: str):
        value = await self.redis.get(key)
        return json.loads(value) if value else None

    async def set(self, key: str, value, ttl: int = 300):
        await self.redis.setex(key, ttl, json.dumps(value))

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def delete_pattern(self, pattern: str):
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

# Cache key conventions:
# drug:{id}           → single drug
# drugs:list:{hash}   → drug list with query hash
# patient:{id}        → single patient
```

### 8. Elasticsearch Pattern

```python
# services/search_service.py
from elasticsearch import AsyncElasticsearch

class SearchService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es = es_client
        self.index = settings.elasticsearch_index_drugs

    async def search_drugs(self, query: str, size: int = 10):
        response = await self.es.search(
            index=self.index,
            body={
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["name^3", "generic_name^2", "category"],
                        "fuzziness": "AUTO",    # typo tolerance
                        "type": "best_fields"
                    }
                },
                "suggest": {
                    "drug_suggest": {
                        "prefix": query,
                        "completion": {"field": "name_suggest"}
                    }
                },
                "size": size
            }
        )
        return response["hits"]["hits"]
```

### 9. Pagination — Always This Pattern

```python
# models/common.py
from pydantic import BaseModel

class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"   # asc | desc

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

# Usage in routes:
@router.get("/drugs")
async def list_drugs(
    pagination: PaginationParams = Depends(),
    category: str | None = None,
    service: DrugService = Depends(get_drug_service),
):
    drugs, total = await service.list(pagination, category)
    return paginated_response(data=drugs, total=total,
                               page=pagination.page,
                               per_page=pagination.per_page)
```

### 10. Testing Pattern

```python
# Unit test — mock db, test service logic
async def test_drug_not_found():
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    service = DrugService(db=mock_db)
    with pytest.raises(DrugNotFoundException):
        await service.get_by_id(99999)

# Integration test — real db, test endpoint
async def test_create_prescription(async_client, doctor_token):
    response = await async_client.post(
        "/api/v1/prescriptions",
        json={"patient_id": 1, "items": [{"drug_id": 1, "dosage": "500mg"}]},
        headers={"Authorization": f"Bearer {doctor_token}"}
    )
    assert response.status_code == 201
    assert response.json()["data"]["status"] == "draft"
    assert response.json()["error"] is None
```

---

## Database — 14 Tables

```
users, profiles, roles, user_roles,
clinics, doctors, patients,
drugs, drug_interactions,
prescriptions, prescription_items,
dispensations, stock_logs, storage_files
```

SQLAlchemy models live in: `app/db/models/`
Alembic migrations live in: `infra/supabase/migrations/`

---

## Environment Variables Reference

All env vars are defined in `.env` and loaded via `app/core/config.py`.
Never access `os.environ` directly. Always use `settings.<variable_name>`.

Key variables:
```
DATABASE_URL          → SQLAlchemy async connection string
REDIS_URL             → Redis connection string
ELASTICSEARCH_URL     → Elasticsearch host
KEYCLOAK_JWKS_URL     → Keycloak JWKS endpoint for JWT validation
OPENAI_API_KEY        → OpenAI API key
SUPABASE_URL          → Supabase project URL
SUPABASE_SERVICE_ROLE_KEY → Supabase service role (server-side only)
```

---

## What Copilot Should NOT Generate

```
❌ Flask routes (@app.route)
❌ Django views, models, or ORM patterns
❌ Synchronous SQLAlchemy (Session, not AsyncSession)
❌ Raw os.getenv() calls
❌ print() statements
❌ Bare try/except without handling
❌ Response format other than {data, error, meta}
❌ Business logic inside route handlers
❌ Direct database calls from route handlers
❌ Any credentials or secrets hardcoded
❌ Blocking I/O operations without async
```

---

## Commit Message Convention

```
feat: add drug interaction checker endpoint
fix: correct stock decrement trigger logic
chore: update dependencies
ci: add pytest to GitHub Actions
docs: update API response format in README
refactor: extract prescription validation to service layer
test: add unit tests for drug service
```
