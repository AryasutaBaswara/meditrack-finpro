from __future__ import annotations

import json

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.core.exceptions import AIServiceException
from app.models.prescription import InteractionCheckResponse


class AIService:
    _GEMINI_API_URL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent"
    )

    def __init__(self, client: AsyncOpenAI | None = None):
        self.client = client

    async def check_drug_interactions(
        self, drug_names: list[str]
    ) -> InteractionCheckResponse:
        provider = settings.openai_provider.lower()

        if provider == "mock":
            return self._mock_interaction_check(drug_names)

        if provider == "gemini":
            return await self._gemini_interaction_check(drug_names)

        if self.client is None:
            raise AIServiceException("OpenAI client has not been initialized")

        drugs = ", ".join(drug_names)
        prompt = (
            f"Check drug interactions for: {drugs}. "
            "Return JSON: {has_interactions: bool, severity: mild|moderate|severe|none, "
            "details: str, drugs_checked: list[str]}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=settings.openai_max_tokens,
                timeout=settings.openai_timeout,
            )
            content = response.choices[0].message.content
            if not content:
                raise AIServiceException("AI service returned an empty response")

            payload = json.loads(content)
            return InteractionCheckResponse.model_validate(payload)
        except RateLimitError as exc:
            raise AIServiceException(
                "OpenAI quota exceeded or billing is unavailable for the configured API key"
            ) from exc
        except APIConnectionError as exc:
            raise AIServiceException("Unable to connect to the OpenAI API") from exc
        except APIStatusError as exc:
            raise AIServiceException(
                f"OpenAI request failed with status {exc.status_code}"
            ) from exc
        except AIServiceException:
            raise
        except Exception as exc:
            raise AIServiceException("Failed to check drug interactions") from exc

    async def _gemini_interaction_check(
        self, drug_names: list[str]
    ) -> InteractionCheckResponse:
        if not settings.gemini_api_key:
            raise AIServiceException(
                "GEMINI_API_KEY is required when OPENAI_PROVIDER=gemini"
            )

        drugs = ", ".join(drug_names)
        prompt = (
            "You are a clinical drug interaction checker. "
            "Return only a compact JSON object with the keys "
            "has_interactions, severity, details, drugs_checked. "
            "Do not include markdown, explanations, or code fences. "
            "Severity must be one of: mild, moderate, severe, none. "
            f"Drugs: {drugs}."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "maxOutputTokens": settings.openai_max_tokens,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }

        try:
            async with httpx.AsyncClient(timeout=settings.openai_timeout) as client:
                response = await client.post(
                    self._GEMINI_API_URL.format(model=settings.gemini_model),
                    params={"key": settings.gemini_api_key},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {401, 403}:
                raise AIServiceException(
                    "Gemini API key is invalid or does not have access"
                ) from exc
            if status_code == 429:
                raise AIServiceException(
                    "Gemini quota exceeded or the free tier limit has been reached"
                ) from exc
            raise AIServiceException(
                f"Gemini request failed with status {status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIServiceException("Unable to connect to the Gemini API") from exc

        try:
            response_payload = response.json()
            candidates = response_payload.get("candidates", [])
            parts = (
                candidates[0].get("content", {}).get("parts", []) if candidates else []
            )
            content = parts[0].get("text") if parts else None
            if not content:
                raise AIServiceException("Gemini returned an empty response")

            payload = json.loads(self._extract_json_object(content))
            return InteractionCheckResponse.model_validate(payload)
        except AIServiceException:
            raise
        except Exception as exc:
            raise AIServiceException(
                "Failed to parse the Gemini interaction response"
            ) from exc

    def _extract_json_object(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIServiceException("Gemini response did not contain a JSON object")

        return stripped[start : end + 1]

    def _mock_interaction_check(
        self, drug_names: list[str]
    ) -> InteractionCheckResponse:
        unique_drugs = list(dict.fromkeys(drug_names))
        normalized = {drug.lower() for drug in unique_drugs}

        if len(unique_drugs) <= 1:
            return InteractionCheckResponse(
                has_interactions=False,
                severity="none",
                details="Mock AI found no clinically significant interactions.",
                drugs_checked=unique_drugs,
            )

        if {
            "amoxicillin 500mg",
            "ibuprofen 400mg",
        }.issubset(normalized):
            return InteractionCheckResponse(
                has_interactions=True,
                severity="moderate",
                details=(
                    "Mock AI flagged a moderate interaction. Monitor gastrointestinal "
                    "side effects and advise the patient to take the medication after meals."
                ),
                drugs_checked=unique_drugs,
            )

        return InteractionCheckResponse(
            has_interactions=True,
            severity="mild",
            details="Mock AI flagged a mild interaction. Review dosing and patient tolerance.",
            drugs_checked=unique_drugs,
        )
