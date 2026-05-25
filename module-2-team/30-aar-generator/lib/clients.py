"""LLM client adapters for the vstack diagnostic patterns.

Every pattern's generator depends on an ``LLMClient`` that exposes a
single synchronous method::

    def complete(self, prompt: str, system: str | None = None) -> str: ...

For async pipelines (server traffic, parallel pattern fan-out), the
matching async adapters expose::

    async def complete(self, prompt: str, system: str | None = None) -> str: ...

Five sync adapters and three async adapters ship with the library:

- ``AnthropicClient`` / ``AnthropicAsyncClient`` — official ``anthropic`` SDK.
- ``OpenAIClient`` / ``OpenAIAsyncClient`` — official ``openai`` SDK
  (Chat Completions).
- ``OllamaClient`` / ``OllamaAsyncClient`` — local Ollama HTTP endpoint,
  for offline / no-API use.
- ``StubClient`` — deterministic in-memory client for tests and benchmarks.

Production-readiness notes
--------------------------
- Every real client has an explicit ``timeout`` argument (default 120s).
  Calls cannot hang indefinitely on a stalled provider.
- Every real client records the most recent token usage on
  ``last_usage`` (an ``LLMUsage`` dataclass). Callers wanting cost
  tracking can read this after each ``complete`` call without changing
  the return signature.
- Install LLM SDKs with the relevant extra
  (``pip install vstack[anthropic]`` / ``[openai]`` / ``[all]``).
  The Ollama adapters only need ``httpx``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_TIMEOUT_SECONDS: float = 120.0


@dataclass
class LLMUsage:
    """Token usage + model metadata for the most recent LLM call.

    All real clients update ``last_usage`` after every ``complete`` call.
    Cost-tracking layers can read this to log spend per pattern run
    without modifying the ``complete(...) -> str`` return signature.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class AnthropicClient:
    """LLMClient adapter for the Anthropic Messages API.

    Install with ``pip install vstack[anthropic]`` (or pin
    ``anthropic>=0.40.0`` yourself).
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        max_tokens: int = 4096,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicClient. "
                "Install with: pip install vstack[anthropic]"
            ) from e
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.last_usage = LLMUsage(model=model)

    def complete(self, prompt: str, system: str | None = None) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.last_usage = LLMUsage(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "input_tokens", 0) or 0)
                + int(getattr(usage, "output_tokens", 0) or 0),
                model=self.model,
            )
        return "".join(block.text for block in response.content if hasattr(block, "text"))


class OpenAIClient:
    """LLMClient adapter for the OpenAI Chat Completions API.

    Install with ``pip install vstack[openai]`` (or pin
    ``openai>=1.50.0`` yourself).
    """

    def __init__(
        self,
        model: str = "gpt-5",
        api_key: str | None = None,
        max_tokens: int = 4096,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "The 'openai' package is required for OpenAIClient. "
                "Install with: pip install vstack[openai]"
            ) from e
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.last_usage = LLMUsage(model=model)

    def complete(self, prompt: str, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=messages,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.last_usage = LLMUsage(
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
                model=self.model,
            )
        return response.choices[0].message.content or ""


class OllamaClient:
    """LLMClient adapter for a local Ollama server.

    Useful for offline development and CI. Default endpoint is
    ``http://localhost:11434``. Install Ollama from ollama.com.
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        max_tokens: int = 4096,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import httpx
        except ImportError as e:
            raise ImportError(
                "The 'httpx' package is required for OllamaClient. Install with: pip install httpx"
            ) from e
        self._httpx = httpx
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.last_usage = LLMUsage(model=model)

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
            f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
        )
        response.raise_for_status()
        body = response.json()
        self.last_usage = LLMUsage(
            input_tokens=int(body.get("prompt_eval_count", 0) or 0),
            output_tokens=int(body.get("eval_count", 0) or 0),
            total_tokens=int(body.get("prompt_eval_count", 0) or 0)
            + int(body.get("eval_count", 0) or 0),
            model=self.model,
        )
        return str(body.get("response", ""))


class AnthropicAsyncClient:
    """Async LLMClient adapter for the Anthropic Messages API.

    Same constructor surface as :class:`AnthropicClient`; expose
    ``async def complete``. Install with ``pip install vstack[anthropic]``.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        max_tokens: int = 4096,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicAsyncClient. "
                "Install with: pip install vstack[anthropic]"
            ) from e
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.last_usage = LLMUsage(model=model)

    async def complete(self, prompt: str, system: str | None = None) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = await self._client.messages.create(**kwargs)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.last_usage = LLMUsage(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "input_tokens", 0) or 0)
                + int(getattr(usage, "output_tokens", 0) or 0),
                model=self.model,
            )
        return "".join(block.text for block in response.content if hasattr(block, "text"))


class OpenAIAsyncClient:
    """Async LLMClient adapter for the OpenAI Chat Completions API."""

    def __init__(
        self,
        model: str = "gpt-5",
        api_key: str | None = None,
        max_tokens: int = 4096,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "The 'openai' package is required for OpenAIAsyncClient. "
                "Install with: pip install vstack[openai]"
            ) from e
        self._client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.last_usage = LLMUsage(model=model)

    async def complete(self, prompt: str, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=messages,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.last_usage = LLMUsage(
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
                model=self.model,
            )
        return response.choices[0].message.content or ""


class OllamaAsyncClient:
    """Async LLMClient adapter for a local Ollama server."""

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        max_tokens: int = 4096,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import httpx
        except ImportError as e:
            raise ImportError(
                "The 'httpx' package is required for OllamaAsyncClient. "
                "Install with: pip install httpx"
            ) from e
        self._httpx = httpx
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.last_usage = LLMUsage(model=model)

    async def complete(self, prompt: str, system: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": self.max_tokens},
        }
        if system:
            payload["system"] = system
        async with self._httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            body = response.json()
        self.last_usage = LLMUsage(
            input_tokens=int(body.get("prompt_eval_count", 0) or 0),
            output_tokens=int(body.get("eval_count", 0) or 0),
            total_tokens=int(body.get("prompt_eval_count", 0) or 0)
            + int(body.get("eval_count", 0) or 0),
            model=self.model,
        )
        return str(body.get("response", ""))


class StubClient:
    """A deterministic stub client useful for unit tests and the synthetic-
    failures benchmark.

    Returns the next pre-canned response from the queue on each call.
    Records every (prompt, system) pair in ``calls`` for assertion.
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []
        self.last_usage = LLMUsage(model="stub")

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        if not self._responses:
            raise RuntimeError("StubClient: no canned responses remaining")
        # Crude tokenizer for stub usage: 1 token per 4 chars (matches the
        # rough OpenAI/Anthropic heuristic well enough for benchmarks).
        prompt_chars = len(prompt) + (len(system) if system else 0)
        body = self._responses.pop(0)
        self.last_usage = LLMUsage(
            input_tokens=max(1, prompt_chars // 4),
            output_tokens=max(1, len(body) // 4),
            total_tokens=max(1, prompt_chars // 4) + max(1, len(body) // 4),
            model="stub",
        )
        return body
