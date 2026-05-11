"""
Anthropic Claude API client for LLM-guided verification.
"""

import os
import logging
from .base import BaseLLMClient
from ..core.config import LLMConfig

logger = logging.getLogger(__name__)


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude client integration."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None
        self._init_client()

    def _init_client(self):
        api_key = os.environ.get(
            self.config.api_key_env
            if self.config.api_key_env != "OPENAI_API_KEY"
            else "ANTHROPIC_API_KEY",
            "",
        )
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, Claude client disabled.")
            return
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            model_name = self.config.model
            if not model_name.startswith("claude"):
                model_name = "claude-sonnet-4-20250514"
        except ImportError:
            logger.warning("anthropic package not installed. Run: pip install anthropic")

    def _call_api(self, prompt: str, system_prompt: str = "") -> str:
        if not self._client:
            raise RuntimeError("Claude client not initialized")

        model_name = self.config.model
        if not model_name.startswith("claude"):
            model_name = "claude-sonnet-4-20250514"

        kwargs = {
            "model": model_name,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        text = response.content[0].text
        if hasattr(response, "usage"):
            self._total_tokens += response.usage.input_tokens + response.usage.output_tokens
        return text
