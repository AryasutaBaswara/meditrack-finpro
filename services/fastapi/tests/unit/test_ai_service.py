from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from openai import APIConnectionError, RateLimitError

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
    client = AsyncMock()
    client.chat.completions.create.side_effect = RateLimitError(
        "quota exceeded",
        response=AsyncMock(status_code=429, request=AsyncMock()),
        body=None,
    )

    with patch("app.services.ai_service.settings.openai_provider", "openai"):
        service = AIService(client=client)

        with pytest.raises(Exception) as exc_info:
            await service.check_drug_interactions(["Paracetamol 500mg"])

    assert "quota exceeded or billing is unavailable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_maps_connection_error_to_clear_message():
    client = AsyncMock()
    client.chat.completions.create.side_effect = APIConnectionError(
        message="connection failed",
        request=Mock(),
    )

    with patch("app.services.ai_service.settings.openai_provider", "openai"):
        service = AIService(client=client)

        with pytest.raises(Exception) as exc_info:
            await service.check_drug_interactions(["Paracetamol 500mg"])

    assert "Unable to connect to the OpenAI API" in str(exc_info.value)
