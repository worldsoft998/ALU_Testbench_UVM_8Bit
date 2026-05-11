"""
OpenAI API client for LLM-guided verification.
"""

import os
import logging
from typing import Optional
from .base import BaseLLMClient
from ..core.config import LLMConfig

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client integration."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None
        self._init_client()

    def _init_client(self):
        api_key = os.environ.get(self.config.api_key_env, "")
        if not api_key:
            logger.warning(f"{self.config.api_key_env} not set, OpenAI client disabled.")
            return
        try:
            import openai
            self._client = openai.OpenAI(api_key=api_key)
        except ImportError:
            logger.warning("openai package not installed. Run: pip install openai")

    def _call_api(self, prompt: str, system_prompt: str = "") -> str:
        if not self._client:
            raise RuntimeError("OpenAI client not initialized")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        result = response.choices[0].message.content
        if response.usage:
            self._total_tokens += response.usage.total_tokens
        return result
