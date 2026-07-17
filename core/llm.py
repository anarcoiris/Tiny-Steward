"""LLM client for llamacpp / OpenAI-compatible endpoints.

Talks to Qwythos (:11440) and Atomic (:11439) via /v1/chat/completions.
Handles streaming, reasoning_content, retry on 503 (slot busy), and token estimation.
"""

from __future__ import annotations

import json
import time
from typing import Any, Generator, Literal

import httpx

from core.backend_gate import Priority, get_gate

StreamPartKind = Literal["reasoning", "content"]


def merge_reasoning_into_content(content: str, reasoning: str) -> str:
    """Embed separate reasoning_content as <think>…</think> when content lacks it."""
    content = content or ""
    reasoning = (reasoning or "").strip()
    if not reasoning:
        return content
    if "<think>" in content:
        return content
    if content:
        return f"<think>\n{reasoning}\n</think>\n\n{content}"
    return f"<think>\n{reasoning}\n</think>"


class LLMClient:
    """Thin wrapper around a llamacpp / OpenAI-compatible chat endpoint."""

    # Keys that belong on LLMClient attrs / nested kwargs — not flat extra_params.
    _RESERVED_CFG = frozenset({
        "base_url", "api", "model", "ctx", "max_tokens", "temperature", "top_p",
        "repeat_penalty", "chat_template_kwargs", "thinking_budget_tokens",
        "cache_prompt", "enable_thinking", "preserve_thinking", "add_vision_id",
        "launch", "id_slot", "provider", "vision",
    })

    def __init__(
        self,
        base_url: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.15,
        top_p: float = 0.9,
        repeat_penalty: float = 1.05,
        timeout: float = 300.0,
        *,
        chat_template_kwargs: dict[str, Any] | None = None,
        thinking_budget_tokens: int | None = -1,
        cache_prompt: bool = True,
        extra_params: dict[str, Any] | None = None,
        gate_lane: Literal["orch", "atomic"] = "orch",
        gate_priority: Priority = "interactive",
        id_slot: int | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.repeat_penalty = repeat_penalty
        self.chat_template_kwargs: dict[str, Any] = dict(chat_template_kwargs or {})
        self.thinking_budget_tokens = thinking_budget_tokens
        self.cache_prompt = cache_prompt
        self.id_slot = int(id_slot) if id_slot is not None else None
        self.extra_params = {
            k: v for k, v in (extra_params or {}).items()
            if k not in self._RESERVED_CFG
        }
        self.gate_lane: Literal["orch", "atomic"] = gate_lane
        self.gate_priority: Priority = gate_priority
        self._last_reasoning: str = ""
        self._last_timings: dict[str, Any] = {}
        self._active_resp: Any = None
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=15.0),
        )

    @classmethod
    def from_lane_config(cls, cfg: dict[str, Any], **overrides: Any) -> "LLMClient":
        """Build a client from a config.yaml llm.orchestrator / llm.atomic block."""
        kwargs = dict(cfg.get("chat_template_kwargs") or {})
        for key in ("enable_thinking", "preserve_thinking", "add_vision_id"):
            if key in cfg and key not in kwargs:
                kwargs[key] = cfg[key]
        budget = cfg.get("thinking_budget_tokens", -1)
        cache = cfg.get("cache_prompt", True)
        known = {
            "base_url", "api", "model", "ctx", "max_tokens", "temperature", "top_p",
            "repeat_penalty", "chat_template_kwargs", "thinking_budget_tokens",
            "cache_prompt", "enable_thinking", "preserve_thinking", "add_vision_id",
            "launch", "id_slot", "provider", "vision",
        }
        extra = {k: v for k, v in cfg.items() if k not in known}
        id_slot = cfg.get("id_slot", None)
        params = {
            "base_url": cfg["base_url"],
            "model": cfg["model"],
            "max_tokens": cfg.get("max_tokens", 4096),
            "temperature": cfg.get("temperature", 0.15),
            "top_p": cfg.get("top_p", 0.9),
            "repeat_penalty": cfg.get("repeat_penalty", 1.05),
            "chat_template_kwargs": kwargs,
            "thinking_budget_tokens": budget,
            "cache_prompt": cache,
            "extra_params": extra,
            "id_slot": id_slot,
        }
        params.update(overrides)
        return cls(**params)

    # ------------------------------------------------------------------
    # Chat completion (non-streaming)
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> str:
        """Send a chat completion request. Returns assistant text (think-merged)."""
        body = self._build_body(
            messages,
            stream=False,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        data = self._post("/v1/chat/completions", body)
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        self._last_reasoning = reasoning
        timings = data.get("timings") if isinstance(data.get("timings"), dict) else {}
        self._last_timings = timings or {}
        return merge_reasoning_into_content(content, reasoning)

    # ------------------------------------------------------------------
    # Chat completion (streaming)
    # ------------------------------------------------------------------
    def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> Generator[str, None, None]:
        """Stream content chunks only (reasoning accumulated on self._last_reasoning)."""
        for kind, text in self.chat_stream_parts(
            messages, max_tokens=max_tokens, temperature=temperature, tools=tools
        ):
            if kind == "content":
                yield text

    def chat_stream_parts(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> Generator[tuple[StreamPartKind, str], None, dict[str, Any] | None]:
        """Stream (kind, text) parts. StopIteration.value is usage/timings dict or None."""
        body = self._build_body(
            messages,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        usage: dict[str, Any] | None = None
        reasoning_parts: list[str] = []
        timings: dict[str, Any] = {}

        try:
            with self._stream_request("/v1/chat/completions", body) as resp:
                self._active_resp = resp
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        if "usage" in chunk and chunk["usage"]:
                            u = chunk["usage"]
                            usage = {
                                "prompt_tokens": u.get("prompt_tokens"),
                                "completion_tokens": u.get("completion_tokens"),
                            }
                        if isinstance(chunk.get("timings"), dict):
                            timings = chunk["timings"]
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        reasoning = delta.get("reasoning_content") or ""
                        if reasoning:
                            reasoning_parts.append(reasoning)
                            yield ("reasoning", reasoning)
                        text = delta.get("content") or ""
                        if text:
                            yield ("content", text)
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
        finally:
            self._active_resp = None

        self._last_reasoning = "".join(reasoning_parts)
        self._last_timings = timings
        if timings:
            usage = dict(usage or {})
            for key in ("cache_n", "prompt_n", "predicted_n", "predicted_ms", "prompt_ms"):
                if key in timings and timings[key] is not None:
                    usage[key] = timings[key]
        return usage

    def abort_active_stream(self) -> None:
        """Best-effort close of an in-flight streaming response (frees llama.cpp slot)."""
        resp = getattr(self, "_active_resp", None)
        if resp is None:
            return
        try:
            resp.close()
        except Exception:
            pass
        self._active_resp = None

    def chat_stream_with_usage(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> Generator[str, None, dict[str, Any] | None]:
        """Stream content chunks; capture usage + reasoning on return.

        Yields text chunks just like chat_stream(). On return (StopIteration),
        the ``value`` attribute holds usage/timings dict or None. Reasoning text is on
        ``self._last_reasoning`` and is also merged by callers via
        :func:`merge_reasoning_into_content`.
        """
        gen = self.chat_stream_parts(
            messages, max_tokens=max_tokens, temperature=temperature, tools=tools
        )
        usage: dict[str, Any] | None = None
        try:
            while True:
                kind, text = next(gen)
                if kind == "content":
                    yield text
        except StopIteration as e:
            usage = e.value
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
        messages: list[dict[str, Any]],
        *,
        stream: bool,
        max_tokens: int | None,
        temperature: float | None,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        # List-valued content (image_url / text parts) is passed through unchanged.
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
            "stream": stream,
            "cache_prompt": self.cache_prompt,
        }
        if self.chat_template_kwargs:
            body["chat_template_kwargs"] = dict(self.chat_template_kwargs)
        if self.thinking_budget_tokens is not None:
            body["thinking_budget_tokens"] = self.thinking_budget_tokens
        if self.id_slot is not None:
            body["id_slot"] = self.id_slot
        if tools is not None:
            body["tools"] = tools
        # extra_params last but must not clobber nested kwargs accidentally
        for k, v in self.extra_params.items():
            if k in ("chat_template_kwargs", "thinking_budget_tokens", "cache_prompt", "id_slot", "launch"):
                continue
            body[k] = v
        return body

    def set_template_kwarg(self, key: str, value: Any) -> None:
        """Update a chat_template_kwargs entry (may invalidate LCP)."""
        self.chat_template_kwargs[key] = value

    def _gate_hold(self):
        return get_gate().hold(self.gate_lane, priority=self.gate_priority)

    def _post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> dict[str, Any]:
        """POST with gate acquire + retry on 503 (slot busy)."""
        with self._gate_hold():
            for attempt in range(max_retries):
                resp = self._client.post(path, json=body)
                if resp.status_code == 503 and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            resp.raise_for_status()
            return resp.json()

    def _stream_request(
        self,
        path: str,
        body: dict[str, Any],
        *,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        """Open a streaming POST under the gate; retry on 503 before yielding.

        The gate slot is held for the lifetime of the returned stream context.
        """
        gate_cm = self._gate_hold()
        gate_cm.__enter__()
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                cm = self._client.stream("POST", path, json=body)
                resp = cm.__enter__()
                if resp.status_code == 503 and attempt < max_retries - 1:
                    resp.read()
                    cm.__exit__(None, None, None)
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                resp.raise_for_status()
                return _GatedStreamContext(cm, resp, gate_cm)
            except httpx.HTTPStatusError as e:
                last_exc = e
                if e.response.status_code == 503 and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                gate_cm.__exit__(None, None, None)
                raise
        gate_cm.__exit__(None, None, None)
        if last_exc:
            raise last_exc
        raise RuntimeError("stream request failed without exception")

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class _GatedStreamContext:
    """Wraps httpx stream context and releases the backend gate on exit."""

    def __init__(self, cm, resp, gate_cm):
        self._cm = cm
        self._resp = resp
        self._gate_cm = gate_cm

    def __enter__(self):
        return self._resp

    def __exit__(self, *args):
        try:
            return self._cm.__exit__(*args)
        finally:
            self._gate_cm.__exit__(None, None, None)


# Keep alias for any external imports
_StreamContext = _GatedStreamContext


# ------------------------------------------------------------------
# Token estimation (rough, no tokenizer dependency)
# ------------------------------------------------------------------
def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def estimate_content_tokens(content: Any) -> int:
    """Estimate tokens for string or multimodal content parts."""
    if isinstance(content, list):
        total = 0
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                total += estimate_tokens(str(part.get("text") or ""))
            elif ptype in ("image_ref", "image_url"):
                # Rough vision-token stand-in; real cost is server-side.
                total += 512
        return total
    return estimate_tokens(content if isinstance(content, str) else str(content or ""))


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        total += estimate_content_tokens(msg.get("content", "") or "")
        rc = msg.get("reasoning_content")
        if isinstance(rc, str):
            total += estimate_tokens(rc)
        total += 4  # role + formatting overhead
    return total
