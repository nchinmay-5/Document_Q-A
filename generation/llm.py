"""LLM access behind one interface, with the provider chosen by settings.

Providers: gemini (hosted), ollama (local), stub (offline development/tests).
"""
import logging
from functools import lru_cache
from typing import Protocol

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the configured provider cannot produce an answer."""


class LLMClient(Protocol):
    name: str

    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...


class GeminiClient:
    """Google Gemini via the google-genai SDK."""

    name = "gemini"

    def __init__(self, api_key: str, model: str, temperature: float, max_output_tokens: int):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set; cannot use the gemini provider.")
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._client = None

    @property
    def client(self):
        # Imported lazily so the SDK is only needed when this provider is used.
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self._temperature,
                max_output_tokens=self._max_output_tokens,
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise LLMError("Gemini returned an empty response.")
        return text


class OllamaClient:
    """Local model served by Ollama."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, temperature: float, max_output_tokens: int, timeout: int):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout = timeout

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self._temperature,
                "num_predict": self._max_output_tokens,
            },
        }
        try:
            response = requests.post(
                f"{self._base_url}/api/chat", json=payload, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc

        if response.status_code >= 400:
            # Ollama reports the real cause (model not pulled, out of memory) in
            # the body, so it belongs in the error.
            raise LLMError(f"Ollama returned {response.status_code}: {response.text[:300]}")

        text = response.json().get("message", {}).get("content", "").strip()
        if not text:
            raise LLMError("Ollama returned an empty response.")
        return text


class StubLLMClient:
    """Deterministic answer for offline development and tests."""

    name = "stub"

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        has_sources = "SOURCE 1" in user_prompt
        return "Stub answer grounded in SOURCE 1. [1]" if has_sources else "No sources supplied."


def _build_gemini_client() -> GeminiClient:
    return GeminiClient(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
    )


def _build_ollama_client() -> OllamaClient:
    return OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        timeout=settings.OLLAMA_TIMEOUT,
    )


_PROVIDERS = {
    "gemini": _build_gemini_client,
    "ollama": _build_ollama_client,
    "stub": StubLLMClient,
}


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """The configured provider, built once per process."""
    provider = settings.LLM_PROVIDER
    builder = _PROVIDERS.get(provider)
    if builder is None:
        supported = ", ".join(sorted(_PROVIDERS))
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Supported: {supported}.")
    logger.info("Using LLM provider %s", provider)
    return builder()
