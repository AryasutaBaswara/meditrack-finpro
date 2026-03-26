from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Any

import httpx
import redis.asyncio as redis
from elasticsearch import AsyncElasticsearch
from fastapi import Depends
from openai import AsyncOpenAI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.services.ai_service import AIService
from app.services.cache_service import CacheService
from app.services.doctor_service import DoctorService
from app.services.drug_service import DrugService
from app.services.patient_service import PatientService
from app.services.prescription_service import PrescriptionService
from app.services.search_service import SearchService

bearer_scheme = HTTPBearer(auto_error=False)

_db_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_client: redis.Redis | None = None
_es_client: AsyncElasticsearch | None = None
_openai_client: AsyncOpenAI | None = None


class TokenData(BaseModel):
    sub: str
    email: str
    roles: list[str]


def set_db_engine(engine: AsyncEngine) -> None:
    global _db_engine, _session_factory
    _db_engine = engine
    _session_factory = async_sessionmaker(engine, expire_on_commit=False)


def set_redis_client(client: redis.Redis) -> None:
    global _redis_client
    _redis_client = client


def set_es_client(client: AsyncElasticsearch) -> None:
    global _es_client
    _es_client = client


def set_openai_client(client: AsyncOpenAI | None) -> None:
    global _openai_client
    _openai_client = client


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Database session factory has not been initialized")

    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


def get_redis() -> redis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client has not been initialized")
    return _redis_client


def get_es() -> AsyncElasticsearch:
    if _es_client is None:
        raise RuntimeError("Elasticsearch client has not been initialized")
    return _es_client


def get_openai() -> AsyncOpenAI | None:
    return _openai_client


def get_cache_service(redis_client: redis.Redis = Depends(get_redis)) -> CacheService:
    return CacheService(redis=redis_client)


def get_search_service(
    es_client: AsyncElasticsearch = Depends(get_es),
) -> SearchService:
    return SearchService(es=es_client)


def get_drug_service(
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service),
    search: SearchService = Depends(get_search_service),
) -> DrugService:
    return DrugService(db=db, cache=cache, search=search)


def get_patient_service(
    db: AsyncSession = Depends(get_db),
) -> PatientService:
    return PatientService(db=db)


def get_doctor_service(
    db: AsyncSession = Depends(get_db),
) -> DoctorService:
    return DoctorService(db=db)


def get_ai_service(client: AsyncOpenAI | None = Depends(get_openai)) -> AIService:
    return AIService(client=client)


def get_prescription_service(
    db: AsyncSession = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
    cache: CacheService = Depends(get_cache_service),
) -> PrescriptionService:
    return PrescriptionService(db=db, ai=ai, cache=cache)


async def _fetch_jwks() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.keycloak_jwks_url)
        response.raise_for_status()
        return response.json()


def _resolve_signing_key(token: str, jwks: dict[str, Any]) -> dict[str, Any]:
    try:
        headers = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise UnauthorizedException("Invalid token header") from exc

    kid = headers.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key

    raise UnauthorizedException("Unable to find a matching signing key")


def _extract_token_data(claims: dict[str, Any]) -> TokenData:
    sub = claims.get("sub")
    email = claims.get("email")
    roles = claims.get("realm_access", {}).get("roles", [])

    if not isinstance(sub, str) or not sub:
        raise UnauthorizedException("Token subject is missing")
    if not isinstance(email, str) or not email:
        raise UnauthorizedException("Token email is missing")
    if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
        raise UnauthorizedException("Token roles are invalid")

    return TokenData(sub=sub, email=email, roles=roles)


async def get_current_user(
    token: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenData:
    if token is None or not token.credentials:
        raise UnauthorizedException("Authentication credentials were not provided")

    try:
        jwks = await _fetch_jwks()
        signing_key = _resolve_signing_key(token.credentials, jwks)
        claims = jwt.decode(
            token.credentials,
            signing_key,
            algorithms=[signing_key.get("alg", "RS256")],
            options={"verify_aud": False},
        )
    except httpx.HTTPError as exc:
        raise UnauthorizedException(
            "Unable to retrieve JWKS for token validation"
        ) from exc
    except JWTError as exc:
        raise UnauthorizedException("Invalid or expired token") from exc

    return _extract_token_data(claims)


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    return current_user


def require_roles(*roles: str) -> Callable[..., TokenData]:
    async def role_checker(
        current_user: TokenData = Depends(get_current_active_user),
    ) -> TokenData:
        if not roles:
            return current_user
        if not any(role in current_user.roles for role in roles):
            raise UnauthorizedException("Insufficient permissions")
        return current_user

    return role_checker
