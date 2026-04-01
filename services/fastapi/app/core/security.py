from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from jose import JWTError, jwt

from app.api.v1.dependencies import TokenData
from app.core.config import settings
from app.core.exceptions import AuthenticationException

_JWKS_CACHE_TTL = 300
_jwks_cache: dict[str, Any] = {"keys": [], "expires_at": 0.0}
_jwks_lock = asyncio.Lock()


def _is_internal_role(role: str) -> bool:
    return role in {"offline_access", "uma_authorization"} or role.startswith(
        "default-roles-"
    )


async def fetch_jwks() -> dict[str, Any]:
    now = time.monotonic()
    if _jwks_cache["keys"] and _jwks_cache["expires_at"] > now:
        return {"keys": list(_jwks_cache["keys"])}

    async with _jwks_lock:
        now = time.monotonic()
        if _jwks_cache["keys"] and _jwks_cache["expires_at"] > now:
            return {"keys": list(_jwks_cache["keys"])}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(settings.keycloak_jwks_url)
                response.raise_for_status()
                jwks = response.json()
        except httpx.HTTPError as exc:
            raise AuthenticationException(
                "Unable to retrieve JWKS for token validation"
            ) from exc

        keys = jwks.get("keys")
        if not isinstance(keys, list) or not keys:
            raise AuthenticationException("JWKS payload is invalid")

        _jwks_cache["keys"] = keys
        _jwks_cache["expires_at"] = time.monotonic() + _JWKS_CACHE_TTL
        return {"keys": list(keys)}


def _get_signing_key(token: str, jwks: dict[str, Any]) -> dict[str, Any]:
    try:
        headers = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthenticationException("Invalid token header") from exc

    kid = headers.get("kid")
    if not isinstance(kid, str) or not kid:
        raise AuthenticationException("Token header is missing kid")

    for key in jwks.get("keys", []):
        if isinstance(key, dict) and key.get("kid") == kid:
            return key

    raise AuthenticationException("Unable to find a matching signing key")


async def decode_token(token: str) -> dict[str, Any]:
    if not token:
        raise AuthenticationException("Authentication token is missing")

    try:
        jwks = await fetch_jwks()
        signing_key = _get_signing_key(token, jwks)
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
        )
    except AuthenticationException:
        raise
    except JWTError as exc:
        raise AuthenticationException("Invalid or expired token") from exc

    if not isinstance(payload, dict):
        raise AuthenticationException("Token payload is invalid")

    return payload


def extract_token_data(payload: dict[str, Any]) -> TokenData:
    sub = payload.get("sub")
    email = payload.get("email")
    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []

    if not isinstance(sub, str) or not sub:
        raise AuthenticationException("Token subject is missing")
    if not isinstance(email, str) or not email:
        raise AuthenticationException("Token email is missing")
    if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
        raise AuthenticationException("Token roles are invalid")

    filtered_roles = [role for role in roles if not _is_internal_role(role)]

    return TokenData(sub=sub, email=email, roles=filtered_roles)
