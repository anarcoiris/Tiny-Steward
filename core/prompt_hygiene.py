"""Detect and scrub REPL / stats chrome from prompts and think previews.

Pasted terminal dumps (box-drawing, ``you ›``, LCP stats) confuse the model
and pollute session history. Encoding is fine; this is content-shape hygiene.
"""

from __future__ import annotations

import re

# Soft block when message is long *and* looks like a REPL dump.
CHROME_LENGTH_THRESHOLD = 400

EMPTY_ASSISTANT_PLACEHOLDER = "[thinking only — no reply text]"

_BOX_RUN = re.compile(r"[\u2500-\u257F]{8,}")
_YOU_PROMPT = re.compile(r"(?:^|\n)\s*you\s*[\u203a>›]\s*", re.IGNORECASE)
_STEWARD_PROMPT = re.compile(r"(?:^|\n)\s*steward\s*[\u2502|]\s*", re.IGNORECASE)
_LCP = re.compile(r"\bLCP\s+\d+", re.IGNORECASE)
_TURN_STATS = re.compile(
    r"(?:^|\n)\s*turn\s+\d+\s*[\u2502|].*?(?:prompt|completion|tok/s)",
    re.IGNORECASE,
)
_PS_PROMPT = re.compile(r"(?:^|\n)\s*PS\s+[A-Za-z]:\\", re.IGNORECASE)
_HEALTH_CHECK = re.compile(r"Orchestrator LLM:\s*http://", re.IGNORECASE)
_SESSION_BANNER = re.compile(r"Tiny Steward\s*[—\-]", re.IGNORECASE)

# Line-level detectors for scrubbing (any hit → drop the line).
_SCRUB_LINE_PATTERNS = (
    re.compile(r"^[\u2500-\u257F\s─═\|\u2502]+$"),
    re.compile(r"you\s*[\u203a>›]", re.IGNORECASE),
    re.compile(r"steward\s*[\u2502|]", re.IGNORECASE),
    re.compile(r"\bLCP\s+\d+", re.IGNORECASE),
    re.compile(r"\bturn\s+\d+\s*[\u2502|]", re.IGNORECASE),
    re.compile(r"Generation slowed to\s+\d", re.IGNORECASE),
    re.compile(r"(?:Orchestrator LLM|Embedder):\s*http://", re.IGNORECASE),
    re.compile(r"Session:\s+\S+.*Skills:", re.IGNORECASE),
    re.compile(r"Commands:\s*/session", re.IGNORECASE),
    re.compile(r"KV prefix may invalidate", re.IGNORECASE),
    re.compile(r"enable_thinking\s*[→\-]", re.IGNORECASE),
    re.compile(r"Manual checkpoint saved", re.IGNORECASE),
    re.compile(r"^PS\s+[A-Za-z]:\\", re.IGNORECASE),
    re.compile(r"tok/s"),
    re.compile(r"Tiny Steward\s*[—\-]"),
    re.compile(r"Loading skill index", re.IGNORECASE),
    re.compile(r"Loaded\s+\d+\s+skills", re.IGNORECASE),
)


def _is_chrome_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _BOX_RUN.search(s) and len(s) > 20:
        return True
    return any(p.search(s) for p in _SCRUB_LINE_PATTERNS)


def looks_like_repl_chrome(text: str) -> bool:
    """True if text contains multiple hallmarks of a pasted steward REPL dump."""
    if not text or not text.strip():
        return False
    hits = 0
    for pat in (
        _BOX_RUN,
        _YOU_PROMPT,
        _STEWARD_PROMPT,
        _LCP,
        _TURN_STATS,
        _PS_PROMPT,
        _HEALTH_CHECK,
        _SESSION_BANNER,
    ):
        if pat.search(text):
            hits += 1
    if _BOX_RUN.search(text) and (_YOU_PROMPT.search(text) or _TURN_STATS.search(text)):
        return True
    if _LCP.search(text) and _TURN_STATS.search(text):
        return True
    return hits >= 3


def should_block_paste(text: str, *, min_chars: int = CHROME_LENGTH_THRESHOLD) -> bool:
    """Refuse ingest when a long message looks like a terminal paste."""
    if len(text) < min_chars:
        return False
    return looks_like_repl_chrome(text)


def paste_block_message() -> str:
    return (
        "Message looks like a pasted REPL/terminal dump (stats, box-drawing, you ›). "
        "Do not paste transcripts into chat — use /attach <path> or @\"path\" instead. "
        "Send a short actionable prompt."
    )


def scrub_chrome(text: str) -> str:
    """Remove chrome-looking lines from content (outbound LLM view)."""
    if not text or not isinstance(text, str):
        return text if isinstance(text, str) else ""
    if not looks_like_repl_chrome(text) and not any(
        p.search(text) for p in (_LCP, _TURN_STATS, _YOU_PROMPT)
    ):
        return text
    kept: list[str] = []
    for line in text.splitlines():
        if _is_chrome_line(line):
            continue
        kept.append(line)
    scrubbed = "\n".join(kept).strip()
    scrubbed = re.sub(r"\n{3,}", "\n\n", scrubbed)
    return scrubbed


def is_chrome_only(text: str) -> bool:
    """True if after scrubbing almost nothing useful remains."""
    if not text or not text.strip():
        return True
    if not looks_like_repl_chrome(text) and not _TURN_STATS.search(text):
        return False
    left = scrub_chrome(text).strip()
    if len(left) < 40:
        return True
    # Still mostly stats fragments
    return bool(_LCP.search(left) or _TURN_STATS.search(left)) and len(left) < 200


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    return _THINK_BLOCK.sub("", text or "").strip()


def think_content_preview(content: str, *, max_chars: int = 500) -> str:
    """Build a think.jsonl content_preview; blank when chrome-only."""
    preview = _strip_think(content or "")[:max_chars]
    if is_chrome_only(preview) or looks_like_repl_chrome(preview):
        cleaned = scrub_chrome(preview)
        if is_chrome_only(cleaned) or len(cleaned.strip()) < 20:
            return ""
        return cleaned[:max_chars]
    return preview
