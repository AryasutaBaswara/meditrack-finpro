from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from openai import APIConnectionError, RateLimitError

from app.core.exceptions import AIServiceException
from app.services.ai_service import AIService


def test_mock_provider_returns_none_for_single_drug():
    with patch("app.services.ai_service.settings.openai_provider", "mock"):
        service = AIService(client=None)

        result = service._mock_interaction_check(["Paracetamol 500mg"])

    assert result.has_interactions is False
    assert result.severity == "none"
    assert result.drugs_checked == ["Paracetamol 500mg"]


def test_mock_provider_returns_moderate_for_seeded_pair():
    with patch("app.services.ai_service.settings.openai_provider", "mock"):
        service = AIService(client=None)

        result = service._mock_interaction_check(
            ["Amoxicillin 500mg", "Ibuprofen 400mg"]
        )

    assert result.has_interactions is True
    assert result.severity == "moderate"


@pytest.mark.asyncio
async def test_openai_provider_maps_rate_limit_to_clear_message():
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    client.chat.completions.create = AsyncMock(
        side_effect=RateLimitError(
            "quota exceeded",
            response=Mock(status_code=429, request=Mock()),
            body=None,
        )
    )

    with patch("app.services.ai_service.settings.openai_provider", "openai"):
        service = AIService(client=client)

        with pytest.raises(Exception) as exc_info:
            await service.check_drug_interactions(["Paracetamol 500mg"])

    assert "quota exceeded or billing is unavailable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_maps_connection_error_to_clear_message():
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    client.chat.completions.create = AsyncMock(
        side_effect=APIConnectionError(
            message="connection failed",
            request=Mock(),
        )
    )

    with patch("app.services.ai_service.settings.openai_provider", "openai"):
        service = AIService(client=client)

        with pytest.raises(Exception) as exc_info:
            await service.check_drug_interactions(["Paracetamol 500mg"])

    assert "Unable to connect to the OpenAI API" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_provider_returns_structured_response():
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "has_interactions": True,
                                    "severity": "mild",
                                    "details": "Gemini found a mild interaction.",
                                    "drugs_checked": [
                                        "Paracetamol 500mg",
                                        "Ibuprofen 400mg",
                                    ],
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post.return_value = response

    with (
        patch("app.services.ai_service.settings.openai_provider", "gemini"),
        patch("app.services.ai_service.settings.gemini_api_key", "test-key"),
        patch("app.services.ai_service.settings.gemini_model", "gemini-2.5-flash"),
        patch("app.services.ai_service.httpx.AsyncClient", return_value=client),
    ):
        service = AIService(client=None)
        result = await service.check_drug_interactions(
            ["Paracetamol 500mg", "Ibuprofen 400mg"]
        )

    assert result.has_interactions is True
    assert result.severity == "mild"
    assert result.drugs_checked == ["Paracetamol 500mg", "Ibuprofen 400mg"]


@pytest.mark.asyncio
async def test_gemini_provider_maps_rate_limit_to_clear_message():
    request = httpx.Request(
        method="POST",
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    )
    response = httpx.Response(status_code=429, request=request)

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post.side_effect = httpx.HTTPStatusError(
        "quota exceeded",
        request=request,
        response=response,
    )

    with (
        patch("app.services.ai_service.settings.openai_provider", "gemini"),
        patch("app.services.ai_service.settings.gemini_api_key", "test-key"),
        patch("app.services.ai_service.httpx.AsyncClient", return_value=client),
    ):
        service = AIService(client=None)

        with pytest.raises(AIServiceException) as exc_info:
            await service.check_drug_interactions(["Paracetamol 500mg"])

    assert "Gemini quota exceeded or the free tier limit has been reached" in str(
        exc_info.value
    )


@pytest.mark.asyncio
async def test_gemini_provider_requires_api_key():
    with (
        patch("app.services.ai_service.settings.openai_provider", "gemini"),
        patch("app.services.ai_service.settings.gemini_api_key", ""),
    ):
        service = AIService(client=None)

        with pytest.raises(AIServiceException) as exc_info:
            await service.check_drug_interactions(["Paracetamol 500mg"])

    assert "GEMINI_API_KEY is required" in str(exc_info.value)
