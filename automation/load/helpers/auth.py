from __future__ import annotations

from urllib.parse import urljoin

import requests


def fetch_access_token(
    *,
    keycloak_base_url: str,
    realm: str,
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
) -> str:
    token_url = urljoin(
        keycloak_base_url.rstrip("/") + "/",
        f"realms/{realm}/protocol/openid-connect/token",
    )
    response = requests.post(
        token_url,
        data={
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Keycloak token response did not contain access_token")
    return token
