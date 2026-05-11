"""
Google Gemini API client for LLM-guided verification.
"""

import os
import logging
from .base import BaseLLMClient
from ..core.config import LLMConfig

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    """Google Gemini client integration."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._model = None
        self._init_client()

    def _init_client(self):
        api_key = os.environ.get(
            self.config.api_key_env
            if self.config.api_key_env != "OPENAI_API_KEY"
            else "GEMINI_API_KEY",
            "",
        )
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, Gemini client disabled.")
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model_name = self.config.model
            if not model_name.startswith("gemini"):
                model_name = "gemini-1.5-flash"
            self._model = genai.GenerativeModel(model_name)
        except ImportError:
            logger.warning(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )

    def _call_api(self, prompt: str, system_prompt: str = "") -> str:
        if not self._model:
            raise RuntimeError("Gemini client not initialized")

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = self._model.generate_content(
            full_prompt,
            generation_config={
                "max_output_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
            },
        )
        return response.text
