"""LLM client for llamacpp / OpenAI-compatible endpoints & Multi-Provider Fallbacks.

Talks to Qwythos (:11440) and Atomic (:11439) via /v1/chat/completions,
with automatic failover to cloud providers (GitHub Models, OpenRouter, Groq, Gemini, Ollama).
Handles streaming, reasoning_content, retry on 503 (slot busy), and token estimation.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Generator, Literal

import httpx

from core.backend_gate import Priority, get_gate
from core.providers.llm_provider import BaseLLMProvider, create_provider_from_config

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
    """Thin wrapper around a llamacpp / OpenAI-compatible chat endpoint with multi-provider fallbacks."""

    # Keys that belong on LLMClient attrs / nested kwargs — not flat extra_params.
    _RESERVED_CFG = frozenset({
        "base_url", "api", "model", "ctx", "max_tokens", "temperature", "top_p", "top_k",
        "repeat_penalty", "chat_template_kwargs", "thinking_budget_tokens",
        "cache_prompt", "enable_thinking", "preserve_thinking", "add_vision_id",
        "launch", "id_slot", "provider", "vision", "fallbacks",
    })

    def __init__(
        self,
        base_url: str,
        model: str,
        max_tokens: int = 16384,
        temperature: float = 0.6,
        top_p: float = 0.95,
        top_k: int = 20,
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
        fallback_providers: list[BaseLLMProvider] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
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
        self.fallback_providers: list[BaseLLMProvider] = list(fallback_providers or [])
        self.active_provider_name: str = "primary"
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
        extra = {k: v for k, v in cfg.items() if k not in cls._RESERVED_CFG}
        id_slot = cfg.get("id_slot", None)

        # Parse fallback providers
        fallbacks_cfg = cfg.get("fallbacks") or []
        fallback_providers: list[BaseLLMProvider] = []
        for idx, fb in enumerate(fallbacks_cfg):
            if isinstance(fb, dict):
                fb_name = fb.get("name", f"fallback_{idx+1}_{fb.get('provider', 'cloud')}")
                try:
                    p = create_provider_from_config(fb_name, fb)
                    fallback_providers.append(p)
                except Exception as e:
                    print(f"  [warn] Failed to initialize fallback provider {fb_name}: {e}")

        params = {
            "base_url": cfg["base_url"],
            "model": cfg["model"],
            "max_tokens": cfg.get("max_tokens", 16384),
            "temperature": cfg.get("temperature", 0.6),
            "top_p": cfg.get("top_p", 0.95),
            "top_k": cfg.get("top_k", 20),
            "repeat_penalty": cfg.get("repeat_penalty", 1.05),
            "chat_template_kwargs": kwargs,
            "thinking_budget_tokens": budget,
            "cache_prompt": cache,
            "extra_params": extra,
            "id_slot": id_slot,
            "fallback_providers": fallback_providers,
        }
        params.update(overrides)
        return cls(**params)

    def get_provider_statuses(self) -> list[dict[str, Any]]:
        """Return health status list for primary and fallback providers."""
        statuses = []
        # Primary status
        start = time.perf_counter()
        primary_healthy = False
        err_msg = None
        try:
            resp = self._client.get("/health", timeout=3.0)
            primary_healthy = (resp.status_code == 200)
        except Exception as e:
            err_msg = str(e)
        lat_ms = round((time.perf_counter() - start) * 1000, 1)

        statuses.append({
            "name": "primary",
            "provider_type": "llamacpp",
            "model": self.model,
            "base_url": self.base_url,
            "healthy": primary_healthy,
            "latency_ms": lat_ms,
            "error": err_msg,
            "active": (self.active_provider_name == "primary"),
        })

        for fb in self.fallback_providers:
            info = fb.check_health()
            info["active"] = (self.active_provider_name == fb.name)
            statuses.append(info)

        return statuses

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
        try:
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
            self.active_provider_name = "primary"
            return merge_reasoning_into_content(content, reasoning)
        except Exception as primary_err:
            if not self.fallback_providers:
                raise primary_err

            for fb_provider in self.fallback_providers:
                try:
                    print(f"\n  [LLM Gateway] Primary endpoint failed ({primary_err}). Falling back to provider: {fb_provider.name} ({fb_provider.model})")
                    res = fb_provider.chat(messages, max_tokens=max_tokens, temperature=temperature, tools=tools)
                    self.active_provider_name = fb_provider.name
                    return res
                except Exception as fb_err:
                    print(f"  [LLM Gateway] Fallback provider {fb_provider.name} failed: {fb_err}")

            raise primary_err

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
        recent_lines: list[str] = []
        repetition_count = 0
        should_abort = False

        try:
            with self._stream_request("/v1/chat/completions", body) as resp:
                self.active_provider_name = "primary"
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

                        buf = reasoning or text
                        if buf and "\n" in buf:
                            for line_item in buf.split("\n")[:-1]:
                                clean_l = line_item.strip()
                                if len(clean_l) > 20:
                                    if recent_lines and clean_l == recent_lines[-1]:
                                        repetition_count += 1
                                        if repetition_count >= 3:
                                            should_abort = True
                                            break
                                    else:
                                        repetition_count = 0
                                        recent_lines.append(clean_l)
                                        if len(recent_lines) > 10:
                                            recent_lines.pop(0)
                        if should_abort:
                            print("\n  [warn] Repetition loop detected during streaming; terminating response early.")
                            break
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
        except Exception as primary_err:
            if not self.fallback_providers:
                raise primary_err

            for fb_provider in self.fallback_providers:
                try:
                    print(f"\n  [LLM Gateway] Primary stream failed ({primary_err}). Falling back to provider: {fb_provider.name} ({fb_provider.model})")
                    self.active_provider_name = fb_provider.name
                    for kind, text in fb_provider.chat_stream(
                        messages, max_tokens=max_tokens, temperature=temperature, tools=tools
                    ):
                        if kind == "reasoning":
                            reasoning_parts.append(text)
                        yield (kind, text)
                    self._last_reasoning = "".join(reasoning_parts)
                    return usage
                except Exception as fb_err:
                    print(f"  [LLM Gateway] Fallback provider {fb_provider.name} failed: {fb_err}")
            raise primary_err
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
        """Stream content chunks; capture usage + reasoning on return."""
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
        """Check if the primary endpoint is reachable and healthy."""
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
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
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
        for k, v in self.extra_params.items():
            if k in ("chat_template_kwargs", "thinking_budget_tokens", "cache_prompt", "id_slot", "launch", "fallbacks"):
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
        """Open a streaming POST under the gate; retry on 503 before yielding."""
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
            except Exception as e:
                last_exc = e
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


_StreamContext = _GatedStreamContext


def estimate_tokens(text: str) -> int:
    """Token estimate using content-type weighting for XML/code syntax vs prose."""
    if not text:
        return 0
    code_chars = sum(len(m.group()) for m in re.finditer(r'<[^>]+>|[\{\}\[\]"`;:\\]', text))
    prose_chars = len(text) - code_chars
    return max(1, int(code_chars / 3.2 + prose_chars / 4.2))


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
        total += 4
    return total
