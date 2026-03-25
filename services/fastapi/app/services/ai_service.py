from __future__ import annotations

import json

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import AIServiceException
from app.models.prescription import InteractionCheckResponse


class AIService:
    def __init__(self, client: AsyncOpenAI):
        self.client = client

    async def check_drug_interactions(
        self, drug_names: list[str]
    ) -> InteractionCheckResponse:
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
        except AIServiceException:
            raise
        except Exception as exc:
            raise AIServiceException("Failed to check drug interactions") from exc
