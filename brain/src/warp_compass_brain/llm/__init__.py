"""LLMProvider — the swap seam over the language model (§13).

DeepSeek now (OpenAI-compatible). The extractor and adjudicator depend only on the ABC, so a
fake provider drives the no-network tests and a vendor swap is one line.
"""

from .base import LLMError, LLMProvider
from .deepseek import DeepSeekProvider

__all__ = ["LLMProvider", "LLMError", "DeepSeekProvider"]
