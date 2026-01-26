"""Pluggable LLM client for grading."""

from __future__ import annotations

import json
import os
import time
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 2.0  # seconds
MAX_BACKOFF = 60.0  # seconds
BACKOFF_MULTIPLIER = 2.0


@dataclass
class LLMResponse:
    """Response from an LLM API call."""

    content: str
    model: str
    usage: dict[str, int] | None = None
    raw_response: dict | None = None


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            system_prompt: System message
            user_prompt: User message
            temperature: Sampling temperature

        Returns:
            LLMResponse with the model's response
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass


class OpenAICompatibleClient(LLMClient):
    """Client for OpenAI-compatible chat completion APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        timeout: float = 120.0,
    ):
        """
        Initialize the OpenAI-compatible client.

        Args:
            api_key: API key (defaults to OPENAI_API_KEY env var)
            base_url: API base URL (defaults to OpenAI)
            model: Model to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Set OPENAI_API_KEY env var or pass api_key parameter."
            )

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        return f"OpenAI-compatible ({self.model})"

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Send a chat completion request with retry logic for rate limits."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        backoff = INITIAL_BACKOFF
        last_exception = None

        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage")

                return LLMResponse(
                    content=content,
                    model=data.get("model", self.model),
                    usage=usage,
                    raw_response=data,
                )

            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code == 429:
                    # Rate limited - apply exponential backoff with jitter
                    jitter = random.uniform(0, backoff * 0.1)
                    sleep_time = min(backoff + jitter, MAX_BACKOFF)
                    print(f"      Rate limited. Retrying in {sleep_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(sleep_time)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                else:
                    # Non-rate-limit error, re-raise immediately
                    raise

        # If we exhausted all retries, raise the last exception
        raise last_exception


class AnthropicClient(LLMClient):
    """Client for Anthropic's Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 120.0,
        max_tokens: int = 4096,
    ):
        """
        Initialize the Anthropic client.

        Args:
            api_key: API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens in response
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Set ANTHROPIC_API_KEY env var or pass api_key parameter."
            )

        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    @property
    def name(self) -> str:
        return f"Anthropic ({self.model})"

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Send a chat completion request with retry logic for rate limits."""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }

        backoff = INITIAL_BACKOFF
        last_exception = None

        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()

                # Extract text from content blocks
                content = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")

                usage = data.get("usage")

                return LLMResponse(
                    content=content,
                    model=data.get("model", self.model),
                    usage=usage,
                    raw_response=data,
                )

            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code == 429:
                    # Rate limited - apply exponential backoff with jitter
                    jitter = random.uniform(0, backoff * 0.1)
                    sleep_time = min(backoff + jitter, MAX_BACKOFF)
                    print(f"      Rate limited. Retrying in {sleep_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(sleep_time)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)
                else:
                    # Non-rate-limit error, re-raise immediately
                    raise

        # If we exhausted all retries, raise the last exception
        raise last_exception


class MockLLMClient(LLMClient):
    """Mock client for testing and dry runs."""

    def __init__(self, response: str | None = None):
        """
        Initialize mock client.

        Args:
            response: Optional fixed response to return
        """
        self._response = response
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    @property
    def name(self) -> str:
        return "Mock LLM"

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Return mock response."""
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt

        if self._response:
            content = self._response
        else:
            # Generate a minimal valid response
            content = json.dumps(
                {
                    "schema_version": "1.0",
                    "route_id": None,
                    "student_id": None,
                    "exercises": [],
                    "overall_summary": "Mock grading - no actual evaluation performed.",
                },
                indent=2,
            )

        return LLMResponse(
            content=content,
            model="mock",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
        )


def create_client(
    provider: str = "openai",
    **kwargs: Any,
) -> LLMClient:
    """
    Factory function to create an LLM client.

    Args:
        provider: Provider name ('openai', 'anthropic', or 'mock')
        **kwargs: Additional arguments passed to the client constructor

    Returns:
        Configured LLMClient instance
    """
    providers = {
        "openai": OpenAICompatibleClient,
        "anthropic": AnthropicClient,
        "mock": MockLLMClient,
    }

    if provider not in providers:
        raise ValueError(
            f"Unknown provider: {provider}. Choose from: {list(providers.keys())}"
        )

    return providers[provider](**kwargs)
