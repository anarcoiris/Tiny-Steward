"""Tool-call / action parsing helpers shared by provider profiles.

Legacy ``<action>`` tags and PRIMARY_ARGS mapping live here.
Dialect-specific ``<tool_call>`` parsers also live here so profiles can
compose them without depending on Runtime.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.primitives import PRIMARY_ARGS

ATTR_PATTERN = re.compile(r'(\w+)="([^"]*)"')
TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
QWEN_PARAM_RE = re.compile(r"<parameter=([^>]+)>\n?(.*?)\n?</parameter>", re.DOTALL)
# Model drift: bare <path>…</path> / <command>…</command> instead of <parameter=…>
BARE_PARAM_RE = re.compile(r"<([a-zA-Z_][\w]*)>\n?(.*?)\n?</\1>", re.DOTALL)
# Hybrid drift: <path>…</parameter> (open bare, close parameter)
DRIFT_PARAM_RE = re.compile(
    r"<(path|content|command|code|pattern|url|method|query|agent|task|note|key|value|tool|body)>"
    r"\n?(.*?)\n?</(?:parameter|\1)>",
    re.DOTALL | re.IGNORECASE,
)
_BARE_PARAM_SKIP = frozenset({
    "tool_call", "function", "think", "thinking", "parameter",
    "tool_response", "tools", "system", "user", "assistant",
})


def args_to_action(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Map tool arguments dict to legacy action shape {name, body, attrs}."""
    primary = PRIMARY_ARGS.get(name)
    attrs = {k: str(v) if v is not None else "" for k, v in args.items()}
    body = ""
    if primary is None:
        body = ""
    elif primary in attrs:
        body = attrs.pop(primary)
    return {"name": name, "body": body, "attrs": attrs}


# Back-compat alias used by older call sites / tests via re-export
_args_to_action = args_to_action


def parse_qwen_tool_call(inner: str) -> dict[str, Any] | None:
    """Parse Qwen JSON body inside ``<tool_call>…</tool_call>``."""
    inner = inner.strip()
    try:
        data = json.loads(inner)
        name = data.get("name")
        args = data.get("arguments", {})
        if isinstance(args, str):
            args = json.loads(args)
        if name and isinstance(args, dict):
            return args_to_action(name, args)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


_parse_qwen_tool_call = parse_qwen_tool_call


def parse_qwythos_tool_call(inner: str) -> dict[str, Any] | None:
    """Parse Qwythos XML ``<function=…><parameter=…>`` inside a tool_call."""
    fn_match = re.search(r"<function=([^>]+)>", inner)
    if not fn_match:
        return None
    name = fn_match.group(1).strip()
    args: dict[str, Any] = {}
    for param_match in QWEN_PARAM_RE.finditer(inner):
        args[param_match.group(1).strip()] = param_match.group(2).strip()
    # Fallback: bare <path>…</path> / hybrid <path>…</parameter>
    if not args or (name in ("write", "append", "read", "mkdir", "ls") and "path" not in args):
        for bare in list(BARE_PARAM_RE.finditer(inner)) + list(DRIFT_PARAM_RE.finditer(inner)):
            key = bare.group(1).strip()
            if key.lower() in _BARE_PARAM_SKIP or key.lower().startswith("parameter"):
                continue
            args.setdefault(key, bare.group(2).strip())
    return args_to_action(name, args)


_parse_qwythos_tool_call = parse_qwythos_tool_call


def parse_actions(text: str) -> list[dict[str, Any]]:
    """Parse legacy <action> tags from LLM response text."""
    actions: list[dict[str, Any]] = []

    for match in re.finditer(r'<action\s+(.*?)>(.*?)</action>', text, re.DOTALL):
        attrs_str = match.group(1)
        body = match.group(2).strip()

        attrs = dict(ATTR_PATTERN.findall(attrs_str))
        name = attrs.pop("name", None)
        if not name:
            continue

        actions.append({
            "name": name,
            "body": body,
            "attrs": attrs,
        })

    return actions


def extract_tool_calls_qwen(text: str) -> list[dict[str, Any]]:
    """Extract Qwen JSON tool calls only (then empty if none)."""
    if "<tool_call>" not in text:
        return []
    actions: list[dict[str, Any]] = []
    for match in TOOL_CALL_RE.finditer(text):
        action = parse_qwen_tool_call(match.group(1))
        if action:
            actions.append(action)
    return actions


def extract_tool_calls_qwythos(text: str) -> list[dict[str, Any]]:
    """Extract Qwythos XML tool calls only (then empty if none)."""
    if "<tool_call>" not in text:
        return []
    actions: list[dict[str, Any]] = []
    for match in TOOL_CALL_RE.finditer(text):
        action = parse_qwythos_tool_call(match.group(1))
        if action:
            actions.append(action)
    return actions


def extract_actions(text: str, *, dialect: str | None = None) -> list[dict[str, Any]]:
    """Extract actions for a dialect, then legacy ``<action>``.

    ``dialect``:
      - ``"qwen_json"`` — JSON tool calls only
      - ``"qwythos_xml"`` — XML tool calls only
      - ``None`` / ``"compat_try_all"`` — try JSON then XML (legacy unified behavior)
    """
    if dialect == "qwen_json":
        actions = extract_tool_calls_qwen(text)
        return actions if actions else parse_actions(text)
    if dialect == "qwythos_xml":
        actions = extract_tool_calls_qwythos(text)
        return actions if actions else parse_actions(text)

    # compat_try_all (default for re-export / older tests)
    if "<tool_call>" in text:
        actions = []
        for match in TOOL_CALL_RE.finditer(text):
            inner = match.group(1)
            action = parse_qwen_tool_call(inner) or parse_qwythos_tool_call(inner)
            if action:
                actions.append(action)
        if actions:
            return actions
    return parse_actions(text)
