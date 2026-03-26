from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from supabase import Client, create_client

from app.api.v1 import router as api_router
from app.api.v1.dependencies import (
    set_db_engine,
    set_es_client,
    set_openai_client,
    set_redis_client,
    set_supabase_client,
)
from app.core.config import settings
from app.core.exceptions import MediTrackException
from app.core.responses import ApiResponse, error_response, success_response

logger = logging.getLogger("meditrack")


def _parse_cors_origins(origins: str) -> list[str]:
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    openai_client: AsyncOpenAI | None = None
    supabase_client: Client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )

    engine: AsyncEngine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
    set_db_engine(engine)
    app.state.db_engine = engine

    redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    await redis_client.ping()
    set_redis_client(redis_client)
    app.state.redis = redis_client

    es_kwargs: dict[str, Any] = {"hosts": [settings.elasticsearch_url]}
    if settings.elasticsearch_username and settings.elasticsearch_password:
        es_kwargs["basic_auth"] = (
            settings.elasticsearch_username,
            settings.elasticsearch_password,
        )
    es_client = AsyncElasticsearch(**es_kwargs)
    await es_client.ping()
    set_es_client(es_client)
    app.state.elasticsearch = es_client

    if settings.openai_provider.lower() == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when OPENAI_PROVIDER=openai")

        openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout,
        )
    set_openai_client(openai_client)
    app.state.openai = openai_client
    set_supabase_client(supabase_client)
    app.state.supabase = supabase_client

    logger.info("MediTrack started")

    try:
        yield
    finally:
        if openai_client is not None:
            await openai_client.close()
        await es_client.close()
        await redis_client.close()
        await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(MediTrackException)
async def meditrack_exception_handler(
    _request: Request,
    exc: MediTrackException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code=exc.code, message=exc.message),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    )
    return JSONResponse(
        status_code=422,
        content=error_response(
            code="VALIDATION_ERROR",
            message=details or "Request validation failed",
        ),
    )


app.include_router(api_router, prefix="/api/v1")


@app.get("/api/v1/health", response_model=ApiResponse[dict[str, str]])
async def health_check() -> dict[str, Any]:
    return success_response(data={"status": "ok", "env": settings.app_env})
