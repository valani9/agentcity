"""
LLM client adapters for the AAR Generator.

The generator depends on an LLMClient that exposes a single method:

    def complete(self, prompt: str, system: str | None = None) -> str: ...

Three adapters ship with the library:

- AnthropicClient — wraps the official `anthropic` SDK.
- OpenAIClient — wraps the official `openai` SDK (Chat Completions).
- OllamaClient — wraps a local Ollama HTTP endpoint, for offline / no-API use.

All adapters are optional: install with the relevant extra
(`pip install agentcity[anthropic]` / `[openai]` / `[all]`). The Ollama
adapter has no install extra because it only needs `httpx`.
"""

from __future__ import annotations

from typing import Any


class AnthropicClient:
    """LLMClient adapter for the Anthropic Messages API.

    Install with `pip install agentcity[anthropic]` (or pin
    `anthropic>=0.40.0` yourself).
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicClient. "
                "Install with: pip install agentcity[anthropic]"
            ) from e
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, prompt: str, system: str | None = None) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        # Anthropic returns a content list; join all text blocks.
        return "".join(
            block.text for block in response.content if hasattr(block, "text")
        )


class OpenAIClient:
    """LLMClient adapter for the OpenAI Chat Completions API.

    Install with `pip install agentcity[openai]` (or pin
    `openai>=1.50.0` yourself).
    """

    def __init__(
        self,
        model: str = "gpt-5",
        api_key: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        try:
            import openai  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "The 'openai' package is required for OpenAIClient. "
                "Install with: pip install agentcity[openai]"
            ) from e
        self._client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, prompt: str, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=messages,  # type: ignore[arg-type]
        )
        return response.choices[0].message.content or ""


class OllamaClient:
    """LLMClient adapter for a local Ollama server.

    Useful for offline development and CI. Default endpoint is
    `http://localhost:11434`. Install Ollama from ollama.com.
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        max_tokens: int = 4096,
    ) -> None:
        try:
            import httpx  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "The 'httpx' package is required for OllamaClient. "
                "Install with: pip install httpx"
            ) from e
        self._httpx = httpx
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens

    def complete(self, prompt: str, system: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": self.max_tokens},
        }
        if system:
            payload["system"] = system
        response = self._httpx.post(
            f"{self.base_url}/api/generate", json=payload, timeout=300
        )
        response.raise_for_status()
        return response.json().get("response", "")


class StubClient:
    """A deterministic stub client useful for unit tests and the synthetic-
    failures benchmark.

    Returns the next pre-canned response from the queue on each call.
    Records every (prompt, system) pair in `calls` for assertion.
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        if not self._responses:
            raise RuntimeError("StubClient: no canned responses remaining")
        return self._responses.pop(0)
