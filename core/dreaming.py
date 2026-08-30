"""Dreaming — consolidate think.jsonl into durable structured memories.

Manual trigger via ``/dream``. Uses the atomic LLM under dream gate priority.
Writes ``sessions/<name>.memory.jsonl`` + ``sessions/<name>.memory.md`` and
advances ``session.metadata["dream_watermark"]``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.prompt_hygiene import is_chrome_only, looks_like_repl_chrome

MEMORY_MD_CAP = 6000
DREAM_INPUT_CAP = 12000

EXTRACT_SYSTEM = """You consolidate a steward session's reasoning traces into durable memory.
Return ONLY a single JSON object (no markdown fences) with this schema:
{
  "facts": [{"statement": str, "evidence_refs": [str], "confidence": float}],
  "validated": [{"statement": str, "evidence_refs": [str], "confidence": float}],
  "falsified": [{"statement": str, "evidence_refs": [str], "confidence": float}],
  "hypotheses": [{"statement": str, "evidence_refs": [str], "confidence": float}],
  "ideas": [{"statement": str, "evidence_refs": [str], "confidence": float}],
  "open_questions": [{"statement": str, "evidence_refs": [str], "confidence": float}]
}
Rules:
- facts = experienced / tool-verified outcomes (paths read, commands that worked).
- validated = claims confirmed by evidence in the traces.
- falsified = claims disproven by evidence.
- hypotheses / ideas = unverified speculation — do not promote to facts.
- evidence_refs: think timestamps (ts) or action names when known.
- confidence in [0,1]. Be concise. Prefer Spanish or English as in the traces.
- Empty arrays are fine. Do not invent tools or files not mentioned.
"""


def think_path(sessions_dir: Path, session_name: str) -> Path:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_name)
    p = Path(sessions_dir) / safe_name
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{session_name}.think.jsonl"


def memory_jsonl_path(sessions_dir: Path, session_name: str) -> Path:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_name)
    p = Path(sessions_dir) / safe_name
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{session_name}.memory.jsonl"


def quarantine_memory_jsonl_path(sessions_dir: Path, session_name: str) -> Path:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_name)
    p = Path(sessions_dir) / "quarantine"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{safe_name}.memory.quarantine.jsonl"


def memory_md_path(sessions_dir: Path, session_name: str) -> Path:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_name)
    p = Path(sessions_dir) / safe_name
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{session_name}.memory.md"


def interactions_path(sessions_dir: Path, session_name: str) -> Path:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_name)
    p = Path(sessions_dir) / safe_name
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{session_name}.interactions.jsonl"


def load_think_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def entries_after_watermark(
    entries: list[dict[str, Any]],
    watermark: str | None,
) -> list[dict[str, Any]]:
    if not watermark:
        return entries
    return [e for e in entries if str(e.get("ts", "")) > watermark]


def filter_dream_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer clean reasoning; skip chrome-only previews without reasoning."""
    kept: list[dict[str, Any]] = []
    for e in entries:
        reasoning = (e.get("reasoning") or "").strip()
        preview = (e.get("content_preview") or "").strip()
        if not reasoning and (is_chrome_only(preview) or looks_like_repl_chrome(preview)):
            continue
        if not reasoning and not preview:
            continue
        kept.append(e)
    return kept


def clean_trace_content(text: str) -> str:
    """Strip raw stacktraces, crash logs, and repetitive error noise before dreaming."""
    if not text:
        return ""
    # Clean full multiline python tracebacks
    cleaned = re.sub(
        r"Traceback \(most recent call last\):[\s\S]*?(?:\n[A-Za-z0-9_.]+(?:Error|Exception|Interrupt)[^\n]*|\n(?=[A-Z#])|\Z)",
        "[traceback stripped]",
        text,
    )
    # Clean repetitive failure notes
    cleaned = re.sub(r"(?:Remediated issue:[^\n]+\n)+", "[remediation loop stripped]\n", cleaned)
    cleaned = re.sub(r"\[aborted:[^\]]+\]", "", cleaned)
    return cleaned.strip()



def compute_traces_sha256(entries: list[dict[str, Any]]) -> str:
    """Calculate cryptographic SHA-256 fingerprint for input reasoning traces."""
    payload = json.dumps(entries, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assess_session_health(
    interactions_p: Path,
    think_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess health of session interactions to prevent memory poisoning."""
    if not interactions_p.exists():
        return {
            "healthy": True,
            "error_rate": 0.0,
            "total_actions": 0,
            "failed_actions": 0,
            "reason": None,
        }

    rows: list[dict[str, Any]] = []
    for line in interactions_p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    total_actions = 0
    failed_actions = 0
    for r in rows:
        actions = r.get("actions")
        if actions is None and "name" in r:
            actions = [r]
        elif actions is None:
            actions = []

        errs = r.get("errors") or []
        if errs:
            failed_actions += len(errs)
            if not actions:
                total_actions += len(errs)

        for a in actions:
            total_actions += 1
            code = a.get("exit_code")
            res = a.get("result")
            if code is None and isinstance(res, dict):
                code = res.get("exit_code")
            preview = str(a.get("body_preview") or "").lower()
            if isinstance(res, dict):
                if res.get("error") or res.get("stderr"):
                    preview += f" {str(res.get('error') or '')} {str(res.get('stderr') or '')}".lower()
            if code is not None and code != 0:
                failed_actions += 1
            elif (
                "traceback (most recent call last)" in preview
                or "error:" in preview
                or "fatal error" in preview
                or "file not found" in preview
                or "permission denied" in preview
                or "out of memory" in preview
                or "[aborted]" in preview
            ):
                failed_actions += 1

    error_rate = failed_actions / max(1, total_actions)

    is_unhealthy = False
    reason = None
    if total_actions >= 3 and error_rate > 0.35:
        is_unhealthy = True
        reason = f"High error rate ({error_rate:.1%}) across {total_actions} actions"
    elif total_actions > 0 and failed_actions == total_actions:
        is_unhealthy = True
        reason = f"All {total_actions} executed actions failed"

    return {
        "healthy": not is_unhealthy,
        "error_rate": round(error_rate, 3),
        "total_actions": total_actions,
        "failed_actions": failed_actions,
        "reason": reason,
    }



def load_recent_actions(path: Path, *, limit: int = 40) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    actions: list[dict[str, Any]] = []
    for r in rows[-20:]:
        for a in r.get("actions") or []:
            actions.append({
                "name": a.get("name"),
                "body_preview": a.get("body_preview"),
                "exit_code": a.get("exit_code"),
                "interaction_ts": r.get("ts"),
            })
            if len(actions) >= limit:
                return actions
    return actions


def build_dream_user_payload(
    think_entries: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> str:
    parts = ["## Think traces (new since last dream)\n"]
    for e in think_entries:
        ts = e.get("ts", "")
        reasoning = (e.get("reasoning") or "").strip()
        preview = (e.get("content_preview") or "").strip()
        block = f"### ts={ts}\n"
        if reasoning:
            sanitized_reasoning = clean_trace_content(reasoning)
            block += f"reasoning:\n{sanitized_reasoning[:2000]}\n"
        if preview and not looks_like_repl_chrome(preview):
            block += f"content_preview:\n{preview[:400]}\n"
        parts.append(block)
    if actions:
        parts.append("\n## Recent tool actions\n")
        parts.append(json.dumps(actions, ensure_ascii=False, indent=2))
    text = "\n".join(parts)
    if len(text) > DREAM_INPUT_CAP:
        text = text[:DREAM_INPUT_CAP] + "\n\n[… truncated for dream budget …]"
    return text


_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_extract_json(raw: str) -> dict[str, Any]:
    """Parse model JSON; tolerate optional markdown fences."""
    text = (raw or "").strip()
    # Drop leading <think> if atomic somehow emitted it
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    # Find outermost object
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("dream extract root must be an object")
    for key in ("facts", "validated", "falsified", "hypotheses", "ideas", "open_questions"):
        val = data.get(key)
        if val is None:
            data[key] = []
        elif not isinstance(val, list):
            raise ValueError(f"dream extract '{key}' must be a list")
    return data


def empty_extract() -> dict[str, Any]:
    return {
        "facts": [],
        "validated": [],
        "falsified": [],
        "hypotheses": [],
        "ideas": [],
        "open_questions": [],
    }


def render_memory_md(session_name: str, extract: dict[str, Any], *, watermark: str) -> str:
    lines = [
        f"# Memory — {session_name}",
        "",
        f"_Last dream watermark: `{watermark}`_",
        "",
    ]

    def _section(title: str, key: str) -> None:
        items = extract.get(key) or []
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("_None._")
            lines.append("")
            return
        for it in items:
            if not isinstance(it, dict):
                continue
            stmt = str(it.get("statement", "")).strip()
            if not stmt:
                continue
            conf = it.get("confidence")
            refs = it.get("evidence_refs") or []
            conf_s = f" (conf={conf})" if conf is not None else ""
            ref_s = f" — refs: {', '.join(str(r) for r in refs[:5])}" if refs else ""
            lines.append(f"- {stmt}{conf_s}{ref_s}")
        lines.append("")

    _section("Facts (experienced)", "facts")
    _section("Validated", "validated")
    _section("Falsified", "falsified")
    _section("Hypotheses", "hypotheses")
    _section("Ideas", "ideas")
    _section("Open questions", "open_questions")
    text = "\n".join(lines)
    if len(text) > MEMORY_MD_CAP:
        text = text[:MEMORY_MD_CAP].rstrip() + "\n\n[… truncated …]\n"
    return text


def memory_summary_for_compact(md_path: Path, *, max_chars: int = 1200) -> str:
    if not md_path.exists():
        return ""
    text = md_path.read_text(encoding="utf-8").strip()
    if not text:
        return ""
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n[…]"
    return text


def memory_block_for_prompt(md_path: Path, *, max_chars: int = 2000) -> str:
    summary = memory_summary_for_compact(md_path, max_chars=max_chars)
    if not summary:
        return ""
    return (
        "## Integrated memories (from /dream)\n\n"
        "These are durable consolidations — prefer them over chat recall:\n\n"
        f"{summary}"
    )


def append_memory_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_dream(
    *,
    sessions_dir: Path | str,
    session_name: str,
    llm: Any,
    watermark: str | None = None,
    force_all: bool = False,
    allow_quarantined: bool = False,
) -> dict[str, Any]:
    """Run one dream cycle. Returns status dict.

    ``llm`` must expose ``.chat(messages, tools=None)`` and ``.gate_priority``.
    Temporarily sets gate_priority to ``dream``.
    """
    sessions_dir = Path(sessions_dir)
    tpath = think_path(sessions_dir, session_name)
    entries = load_think_entries(tpath)
    if force_all:
        slice_ = entries
    else:
        slice_ = entries_after_watermark(entries, watermark)
    slice_ = filter_dream_entries(slice_)
    if not slice_:
        return {
            "ok": True,
            "skipped": True,
            "reason": "no new think entries to dream",
            "watermark": watermark,
            "count": 0,
        }

    ipath = interactions_path(sessions_dir, session_name)
    health = assess_session_health(ipath, slice_)
    if not health["healthy"] and not force_all and not allow_quarantined:
        sha256 = compute_traces_sha256(slice_)
        qrecord = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": session_name,
            "watermark": watermark,
            "quarantined": True,
            "health": health,
            "entry_count": len(slice_),
            "source_think_sha256": sha256,
        }
        qpath = quarantine_memory_jsonl_path(sessions_dir, session_name)
        append_memory_jsonl(qpath, qrecord)
        return {
            "ok": True,
            "skipped": False,
            "quarantined": True,
            "reason": f"Session quarantined to prevent memory poisoning: {health['reason']}",
            "health": health,
            "watermark": watermark,
            "count": len(slice_),
            "quarantine_path": str(qpath),
        }

    actions = load_recent_actions(ipath)
    user_payload = build_dream_user_payload(slice_, actions)
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {"role": "user", "content": user_payload},
    ]

    prev_priority = getattr(llm, "gate_priority", "interactive")
    try:
        llm.gate_priority = "dream"
        raw = llm.chat(messages, tools=None)
    finally:
        llm.gate_priority = prev_priority

    try:
        extract = parse_extract_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "ok": False,
            "error": f"failed to parse dream JSON: {e}",
            "raw_preview": (raw or "")[:500],
        }

    new_wm = str(slice_[-1].get("ts") or datetime.now(timezone.utc).isoformat())
    sha256 = compute_traces_sha256(slice_)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": session_name,
        "watermark": new_wm,
        "entry_count": len(slice_),
        "extract": extract,
        "manifest": {
            "source_think_sha256": sha256,
            "health": health,
        },
    }
    append_memory_jsonl(memory_jsonl_path(sessions_dir, session_name), record)
    md = render_memory_md(session_name, extract, watermark=new_wm)
    memory_md_path(sessions_dir, session_name).write_text(md, encoding="utf-8")

    return {
        "ok": True,
        "skipped": False,
        "quarantined": False,
        "watermark": new_wm,
        "count": len(slice_),
        "memory_md": str(memory_md_path(sessions_dir, session_name)),
        "extract_counts": {k: len(extract.get(k) or []) for k in extract},
        "manifest": record["manifest"],
    }

