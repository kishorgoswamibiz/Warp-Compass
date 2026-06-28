"""DeepSeek implementation of ``LLMProvider`` (OpenAI-compatible API).

Uses the official ``openai`` SDK pointed at DeepSeek's base URL. The SDK retries transient
errors and honors ``Retry-After`` on 429; we add a tolerant JSON parse on top.
"""

from __future__ import annotations

import json

from ..config import Settings, get_settings
from .base import LLMError, LLMProvider


def _loads_tolerant(text: str) -> dict:
    """Parse JSON, tolerating a ```json ... ``` fence if the model adds one."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.removeprefix("json").strip()
        if s.endswith("```"):
            s = s[: -3].strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as e:
        raise LLMError(f"model did not return valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise LLMError(f"model returned JSON of type {type(obj).__name__}, expected object")
    return obj


class DeepSeekProvider(LLMProvider):
    """Batch-tier model (default ``deepseek-v4-pro``) for extraction + adjudication."""

    def __init__(self, settings: Settings | None = None, *, model: str | None = None) -> None:
        self._s = settings or get_settings()
        if not self._s.deepseek_api_key:
            raise LLMError(
                "DEEPSEEK_API_KEY is empty. Set it in brain/.env (and save the file)."
            )
        self.model = model or self._s.deepseek_model_batch
        # Imported here so the package imports cleanly even if `openai` isn't installed yet.
        from openai import OpenAI

        self._client = OpenAI(
            api_key=self._s.deepseek_api_key,
            base_url=self._s.deepseek_base_url,
            max_retries=5,  # SDK honors Retry-After on 429 / transient errors
        )

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception as e:  # network/auth/rate-limit after retries
            raise LLMError(f"DeepSeek call failed: {type(e).__name__}: {e}") from e
        content = resp.choices[0].message.content if resp.choices else ""
        return _loads_tolerant(content)

    def list_models(self) -> list[str]:
        """Return model IDs the key can access — used by `cli check-models`."""
        return [m.id for m in self._client.models.list().data]
