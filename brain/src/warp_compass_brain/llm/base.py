"""The ``LLMProvider`` interface.

Deliberately tiny: one strict-JSON call is all the batch pipeline needs (extractor +
adjudicator both want JSON out). Implementations handle retry/backoff internally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    """Raised when the model call fails after retries, or returns unparseable JSON."""


class LLMProvider(ABC):
    @abstractmethod
    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict:
        """Send a system+user prompt and return the parsed JSON object the model emits.

        Implementations must request JSON mode where the vendor supports it, retry on
        rate-limit/transient errors (honoring ``Retry-After``), and raise ``LLMError`` if the
        result still isn't valid JSON.
        """
