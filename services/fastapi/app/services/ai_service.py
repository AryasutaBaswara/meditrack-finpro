from __future__ import annotations

import json

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.core.exceptions import AIServiceException
from app.models.prescription import InteractionCheckResponse


class AIService:
    def __init__(self, client: AsyncOpenAI | None = None):
        self.client = client

    async def check_drug_interactions(
        self, drug_names: list[str]
    ) -> InteractionCheckResponse:
        if settings.openai_provider.lower() == "mock":
            return self._mock_interaction_check(drug_names)

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
