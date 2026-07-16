"""LLM client for llamacpp / OpenAI-compatible endpoints.

Talks to Qwythos (:11440) and Atomic (:11439) via /v1/chat/completions.
Handles streaming, retry on 503 (slot busy), and token estimation.
"""

from __future__ import annotations

import json
import time
from typing import Any, Generator

import httpx


class LLMClient:
    """Thin wrapper around a llamacpp / OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.15,
        top_p: float = 0.9,
        repeat_penalty: float = 1.05,
        timeout: float = 300.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.repeat_penalty = repeat_penalty
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=15.0),
        )

    # ------------------------------------------------------------------
    # Chat completion (non-streaming)
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a chat completion request. Returns the assistant message text."""
        body = self._build_body(
            messages,
            stream=False,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        data = self._post("/v1/chat/completions", body)
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Chat completion (streaming)
    # ------------------------------------------------------------------
    def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Stream a chat completion. Yields text chunks."""
        body = self._build_body(
            messages,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        with self._client.stream("POST", "/v1/chat/completions", json=body) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        yield text
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    def chat_stream_with_usage(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, dict[str, int] | None]:
        """Stream a chat completion and capture usage stats from the final chunk.

        Yields text chunks just like chat_stream(). On return (StopIteration),
        the ``value`` attribute of the StopIteration exception holds a dict
        ``{"prompt_tokens": int, "completion_tokens": int}`` if the server
        sent usage data, or ``None`` otherwise.

        Typical usage::

            gen = llm.chat_stream_with_usage(messages)
            try:
                while True:
                    chunk = next(gen)
                    print(chunk, end="")
            except StopIteration as e:
                usage = e.value   # dict or None
        """
        body = self._build_body(
            messages,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        usage: dict[str, int] | None = None

        with self._client.stream("POST", "/v1/chat/completions", json=body) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    # Capture usage if the server includes it (common in
                    # llamacpp ≥ b3200 with --log-disable disabled)
                    if "usage" in chunk and chunk["usage"]:
                        u = chunk["usage"]
                        usage = {
                            "prompt_tokens": u.get("prompt_tokens"),
                            "completion_tokens": u.get("completion_tokens"),
                        }
                    delta = chunk["choices"][0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        yield text
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

        return usage


    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    def health(self) -> bool:
        """Check if the endpoint is reachable and healthy."""
        try:
            resp = self._client.get("/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_body(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        max_tokens: int | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
            "stream": stream,
        }

    def _post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> dict[str, Any]:
        """POST with retry on 503 (slot busy)."""
        for attempt in range(max_retries):
            resp = self._client.post(path, json=body)
            if resp.status_code == 503 and attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        # Should not reach here, but just in case
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ------------------------------------------------------------------
# Token estimation (rough, no tokenizer dependency)
# ------------------------------------------------------------------
def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4  # role + formatting overhead
    return total
