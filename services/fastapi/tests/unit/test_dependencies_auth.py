from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError

from app.api.v1 import dependencies
from app.core.exceptions import AuthenticationException, UnauthorizedException
from app.models.auth import TokenData


def test_extract_token_data_returns_token_data():
    claims = {
        "sub": "user-1",
        "email": "user@example.com",
        "realm_access": {"roles": ["doctor", "admin"]},
    }

    result = dependencies._extract_token_data(claims)

    assert result == TokenData(
        sub="user-1",
        email="user@example.com",
        roles=["doctor", "admin"],
    )


@pytest.mark.parametrize(
    ("claims", "message"),
    [
        (
            {"email": "user@example.com", "realm_access": {"roles": []}},
            "Token subject is missing",
        ),
        ({"sub": "user-1", "realm_access": {"roles": []}}, "Token email is missing"),
        (
            {
                "sub": "user-1",
                "email": "user@example.com",
                "realm_access": {"roles": "doctor"},
            },
            "Token roles are invalid",
        ),
    ],
)
def test_extract_token_data_rejects_invalid_claims(claims, message):
    with pytest.raises(AuthenticationException, match=message):
        dependencies._extract_token_data(claims)


def test_resolve_signing_key_returns_matching_key():
    jwks = {"keys": [{"kid": "match", "alg": "RS256"}]}

    with patch(
        "app.api.v1.dependencies.jwt.get_unverified_header",
        return_value={"kid": "match"},
    ):
        result = dependencies._resolve_signing_key("token", jwks)

    assert result == {"kid": "match", "alg": "RS256"}


def test_resolve_signing_key_rejects_invalid_header():
    with patch(
        "app.api.v1.dependencies.jwt.get_unverified_header",
        side_effect=JWTError("bad header"),
    ):
        with pytest.raises(AuthenticationException, match="Invalid token header"):
            dependencies._resolve_signing_key("token", {"keys": []})


def test_resolve_signing_key_rejects_missing_kid():
    with patch(
        "app.api.v1.dependencies.jwt.get_unverified_header",
        return_value={"kid": "missing"},
    ):
        with pytest.raises(
            AuthenticationException, match="Unable to find a matching signing key"
        ):
            dependencies._resolve_signing_key("token", {"keys": [{"kid": "other"}]})


@pytest.mark.asyncio
async def test_get_current_user_requires_credentials():
    with pytest.raises(
        AuthenticationException, match="Authentication credentials were not provided"
    ):
        await dependencies.get_current_user(None)


@pytest.mark.asyncio
async def test_get_current_user_maps_http_error_from_jwks_fetch():
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    with patch(
        "app.api.v1.dependencies._fetch_jwks",
        new=AsyncMock(side_effect=httpx.HTTPError("boom")),
    ):
        with pytest.raises(
            AuthenticationException,
            match="Unable to retrieve JWKS for token validation",
        ):
            await dependencies.get_current_user(token)


@pytest.mark.asyncio
async def test_get_current_user_maps_jwt_error():
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    with patch(
        "app.api.v1.dependencies._fetch_jwks", new=AsyncMock(return_value={"keys": []})
    ), patch(
        "app.api.v1.dependencies._resolve_signing_key",
        side_effect=JWTError("bad token"),
    ):
        with pytest.raises(AuthenticationException, match="Invalid or expired token"):
            await dependencies.get_current_user(token)


@pytest.mark.asyncio
async def test_get_current_user_returns_token_data():
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    claims = {
        "sub": "user-1",
        "email": "user@example.com",
        "realm_access": {"roles": ["doctor"]},
    }

    with patch(
        "app.api.v1.dependencies._fetch_jwks",
        new=AsyncMock(return_value={"keys": [{"kid": "match", "alg": "RS256"}]}),
    ), patch(
        "app.api.v1.dependencies._resolve_signing_key",
        return_value={"kid": "match", "alg": "RS256"},
    ), patch(
        "app.api.v1.dependencies.jwt.decode", return_value=claims
    ):
        result = await dependencies.get_current_user(token)

    assert result == TokenData(sub="user-1", email="user@example.com", roles=["doctor"])


@pytest.mark.asyncio
async def test_get_current_db_user_returns_user():
    db = Mock()
    db.execute = AsyncMock(
        return_value=Mock(scalar_one_or_none=Mock(return_value="user-object"))
    )

    result = await dependencies.get_current_db_user(
        TokenData(sub="user-1", email="user@example.com", roles=["doctor"]),
        db,
    )

    assert result == "user-object"


@pytest.mark.asyncio
async def test_get_current_db_user_raises_when_missing():
    db = Mock()
    db.execute = AsyncMock(
        return_value=Mock(scalar_one_or_none=Mock(return_value=None))
    )

    with pytest.raises(
        AuthenticationException, match="Authenticated user was not found"
    ):
        await dependencies.get_current_db_user(
            TokenData(sub="user-1", email="user@example.com", roles=["doctor"]),
            db,
        )


@pytest.mark.asyncio
async def test_require_roles_allows_matching_role():
    checker = dependencies.require_roles("doctor")

    result = await checker(
        TokenData(sub="user-1", email="user@example.com", roles=["doctor"])
    )

    assert result.roles == ["doctor"]


@pytest.mark.asyncio
async def test_require_roles_rejects_non_matching_role():
    checker = dependencies.require_roles("doctor")

    with pytest.raises(UnauthorizedException, match="Insufficient permissions"):
        await checker(
            TokenData(sub="user-1", email="user@example.com", roles=["patient"])
        )


@pytest.mark.asyncio
async def test_require_roles_without_args_allows_any_authenticated_user():
    checker = dependencies.require_roles()

    result = await checker(
        TokenData(sub="user-1", email="user@example.com", roles=["patient"])
    )

    assert result.roles == ["patient"]
