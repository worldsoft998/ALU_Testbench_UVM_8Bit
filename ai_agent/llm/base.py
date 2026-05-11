"""
Base class for LLM client integrations.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional
from ..core.config import LLMConfig
from .prompt_templates import PromptTemplates

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.templates = PromptTemplates()
        self._call_count = 0
        self._total_tokens = 0

    @abstractmethod
    def _call_api(self, prompt: str, system_prompt: str = "") -> str:
        """Make API call to the LLM provider. Returns response text."""
        pass

    def get_seed_strategy(self, coverage_data: dict) -> Optional[dict]:
        """
        Ask the LLM to suggest a seed/stimulus strategy based on coverage gaps.
        Uses minimal tokens by sending structured data and requesting JSON output.
        """
        prompt = self.templates.seed_strategy_prompt(coverage_data)
        system = self.templates.SYSTEM_PROMPT

        try:
            response = self._call_api(prompt, system)
            self._call_count += 1
            return self._parse_strategy_response(response)
        except Exception as e:
            logger.warning(f"LLM seed strategy request failed: {e}")
            return None

    def analyze_coverage_gaps(self, gaps: list) -> Optional[str]:
        """Ask LLM to analyze coverage gaps and suggest targeted approaches."""
        prompt = self.templates.gap_analysis_prompt(gaps)
        system = self.templates.SYSTEM_PROMPT

        try:
            response = self._call_api(prompt, system)
            self._call_count += 1
            return response
        except Exception as e:
            logger.warning(f"LLM gap analysis failed: {e}")
            return None

    def suggest_constraint_adjustment(self, current_state: dict) -> Optional[dict]:
        """Ask LLM to suggest constraint/distribution adjustments."""
        prompt = self.templates.constraint_prompt(current_state)
        system = self.templates.SYSTEM_PROMPT

        try:
            response = self._call_api(prompt, system)
            self._call_count += 1
            return self._parse_constraint_response(response)
        except Exception as e:
            logger.warning(f"LLM constraint suggestion failed: {e}")
            return None

    def _parse_strategy_response(self, response: str) -> Optional[dict]:
        """Parse LLM strategy response into structured data."""
        try:
            # Try to extract JSON from response
            json_match = response
            if "```json" in response:
                json_match = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_match = response.split("```")[1].split("```")[0]

            return json.loads(json_match.strip())
        except (json.JSONDecodeError, IndexError):
            # Fall back to extracting key info from text
            return {"raw_suggestion": response, "seeds": [], "strategy": "explore"}

    def _parse_constraint_response(self, response: str) -> Optional[dict]:
        """Parse constraint adjustment response."""
        return self._parse_strategy_response(response)

    def get_stats(self) -> dict:
        """Return LLM usage statistics."""
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "api_calls": self._call_count,
            "total_tokens": self._total_tokens,
        }
