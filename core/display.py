"""Display layer — all terminal rendering for Tiny Steward.

Uses `rich` when available (strongly recommended). Falls back to plain
print() if import fails so the runtime never crashes on a bad install.

Public API
----------
banner()                       Print the startup banner.
prompt_text()                  Return the styled "you › " prompt string.
print_response(text, *, stream_chunks)
                               Print the steward's reasoning text.
print_result(name, text, *, is_error)
                               Print an action result box.
print_stats(stats)             Print the per-turn stats line.
print_event(kind, message)     Print a special event (compaction, checkpoint …).
print_config_table(rows)       Print a configuration table.
print_session_table(sessions)  Print a sessions listing.
print_skills_table(skills)     Print an indexed skills listing.
"""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.stats import TurnStats, SessionStats

# ---------------------------------------------------------------------------
# Rich bootstrap — graceful fallback
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.rule import Rule
    from rich import box
    from rich.style import Style
    _RICH = True
except ImportError:  # pragma: no cover
    _RICH = False

# One shared console — stderr=False, highlight=False to avoid over-parsing
if _RICH:
    import sys as _sys
    import io as _io
    _stdout = _sys.stdout
    # On Windows the default console may be cp1252; rewrap to UTF-8 so rich
    # can render emoji and box-drawing characters without UnicodeEncodeError.
    if hasattr(_stdout, "buffer") and getattr(_stdout, "encoding", "").lower() not in (
        "utf-8", "utf_8", "utf8"
    ):
        _stdout = _io.TextIOWrapper(
            _stdout.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )
    _console = Console(highlight=False, soft_wrap=True, file=_stdout)
else:  # pragma: no cover
    _console = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Theme palette
# ---------------------------------------------------------------------------
class _C:
    """Color / style constants (Dark hex theme)."""
    BRAND   = "bold #5EEAD4"   # teal-400
    STEWARD = "bold #5EEAD4"
    USER    = "bold #F8FAFC"   # white
    DIM     = "dim #94A3B8"    # slate-400
    OK      = "bold #4ADE80"   # green-400
    WARN    = "bold #FBBF24"   # amber-400
    ERROR   = "bold #F87171"   # red-400
    INFO    = "bold #60A5FA"   # blue-400
    BORDER  = "#334155"        # slate-700
    STAT    = "dim #94A3B8"
    HEADER  = "bold #C084FC"   # purple-400
    ACCENT  = "#FB923C"        # orange-400


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _plain_print(text: str, **_):
    """Fallback renderer when rich is unavailable."""
    print(text)


def _p(renderable=None, *, markup: bool = True, **kwargs):
    """Shortcut: print via rich console or plain fallback."""
    if _RICH and _console:
        _console.print(renderable, markup=markup, **kwargs)
    else:
        _plain_print(str(renderable))


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
def banner(session_name: str, skills_count: int, *, color: bool = True):
    """Print the startup banner."""
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not _RICH:
        print("\n  Tiny Steward — Semantic Capability Graph")
        print("  ─────────────────────────────────────────")
        print(f"  Session: {session_name}  │  Skills: {skills_count}  │  {now_str}")
        print("  Commands: /session <name>, /sessions, /set, /stats, /quit")
        return

    _console.print()
    _console.rule(
        f"[{_C.BRAND}]Tiny Steward[/{_C.BRAND}] [dim]\u2014 Semantic Capability Graph[/dim]",
        style=_C.BORDER,
    )
    _console.print(
        f"  [dim]Session:[/dim] [bold]{session_name}[/bold]"
        f"   [dim]│[/dim]   [dim]Skills:[/dim] [bold]{skills_count}[/bold]"
        f"   [dim]│[/dim]   [dim]{now_str}[/dim]",
    )
    _console.print(
        "  [dim]Commands:[/dim] "
        f"[{_C.BRAND}]/session[/{_C.BRAND}] [dim]<name>[/dim]  "
        f"[{_C.BRAND}]/sessions[/{_C.BRAND}]  "
        f"[{_C.BRAND}]/set[/{_C.BRAND}]  "
        f"[{_C.BRAND}]/stats[/{_C.BRAND}]  "
        f"[{_C.BRAND}]/checkpoint[/{_C.BRAND}]  "
        f"[{_C.BRAND}]/skills[/{_C.BRAND}]  "
        f"[{_C.BRAND}]/help[/{_C.BRAND}] [dim]<query>[/dim]  "
        f"[{_C.BRAND}]/review[/{_C.BRAND}]  "
        f"[{_C.BRAND}]/quit[/{_C.BRAND}]",
    )
    _console.rule(style=_C.BORDER)
    _console.print()


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def prompt_text() -> str:
    """Return the plain-text prompt string (used with input())."""
    if _RICH:
        # Build a styled prompt; rich.console.input would suppress readline so
        # we return the raw string and let the caller pass it to input().
        return "  \x1b[1;37myou\x1b[0m \x1b[2m›\x1b[0m "
    return "  you › "


# ---------------------------------------------------------------------------
# Response printing (LLM output)
# ---------------------------------------------------------------------------
# Strip <action …>…</action> tags, replace with a dim placeholder
_ACTION_RE = re.compile(r"<action\s+.*?>.*?</action>", re.DOTALL)
_THINK_RE  = re.compile(r"<think>.*?</think>", re.DOTALL)


def _clean_response(text: str) -> str:
    """Remove action/tool-call tags for display; keep <think> visible."""
    text = _ACTION_RE.sub("\x1b[2m[action]\x1b[0m", text)
    text = re.sub(r"<tool_call>.*?</tool_call>", "\x1b[2m[tool_call]\x1b[0m", text, flags=re.DOTALL)
    return text.strip()


def print_response(text: str, *, markdown: bool = True):
    """Print a steward response, optionally rendered as Markdown."""
    clean = _clean_response(text)
    if not clean:
        return

    if not _RICH:
        for line in clean.split("\n"):
            print(f"  steward │ {line}")
        return

    # Prefix label
    _console.print("  [bold bright_cyan]steward[/bold bright_cyan] [dim]│[/dim]")

    if markdown:
        # Render as Markdown, indented
        md = Markdown(clean, code_theme="monokai")
        _console.print(md, no_wrap=False)
    else:
        for line in clean.split("\n"):
            _console.print(f"  {line}", markup=False)


def print_response_stream_start():
    """Print the steward prefix before streaming begins."""
    if _RICH:
        _console.print("  [bold bright_cyan]steward[/bold bright_cyan] [dim]│[/dim]")
    else:
        print("  steward │ ", end="", flush=True)


def print_stream_chunk(chunk: str):
    """Print a single streaming token chunk (no newline flushing)."""
    if _RICH:
        _console.print(chunk, end="", markup=False, highlight=False)
    else:
        print(chunk, end="", flush=True)


def print_stream_end():
    """Finish the streaming line and flush."""
    if _RICH:
        _console.print()
    else:
        print()


def print_action_placeholder(name: str, body: str = ""):
    """Print a dim placeholder for an action that was streamed past."""
    icons = {
        "pwsh": "⚙️", "bash": "🐚", "python": "🐍", "read": "📄",
        "write": "✏️", "append": "✏️", "mkdir": "📁", "ls": "📋",
        "grep": "🔍", "http": "🌐", "mcp": "🔌", "delegate": "🤝",
        "help": "💡"
    }
    icon = icons.get(name, "↳")
    preview = body.replace("\n", " ").strip()
    if len(preview) > 60:
        preview = preview[:59] + "…"

    if _RICH:
        if preview:
            _console.print(f"  [dim]{icon} executing [{_C.ACCENT}]{name}[/{_C.ACCENT}]  {preview}[/dim]")
        else:
            _console.print(f"  [dim]{icon} executing [{_C.ACCENT}]{name}[/{_C.ACCENT}] …[/dim]")
    else:
        if preview:
            print(f"  {icon} executing {name}  {preview}")
        else:
            print(f"  {icon} executing {name} …")


# ---------------------------------------------------------------------------
# Result boxes
# ---------------------------------------------------------------------------
def print_result(name: str, text: str, *, is_error: bool = False):
    """Print an action result in a styled box."""
    if not _RICH:
        lines = text.split("\n")
        max_lines = 30
        print(f"  ── {name} ──")
        for line in lines[:max_lines]:
            print(f"  │ {line}")
        if len(lines) > max_lines:
            print(f"  │ … ({len(lines) - max_lines} more lines)")
        print("  └──────────")
        return

    border_style = _C.ERROR if is_error else _C.BORDER
    title_style  = _C.ERROR if is_error else _C.OK

    # Truncate long output
    lines = text.split("\n")
    max_lines = 40
    display_text = text
    truncated = ""
    if len(lines) > max_lines:
        display_text = "\n".join(lines[:max_lines])
        truncated = f"\n[dim]… {len(lines) - max_lines} more lines[/dim]"

    from rich.syntax import Syntax
    # Very basic content-type detection
    panel_content: str | Syntax = f"[white]{display_text}[/white]"
    if display_text.strip().startswith("{") and display_text.strip().endswith("}"):
        panel_content = Syntax(display_text, "json", theme="monokai", background_color="default", word_wrap=True)
    elif name == "python" and "Traceback" in display_text:
        # A bit of manual coloring for tracebacks
        colored_err = display_text.replace("Traceback (most recent call last):", f"[{_C.ERROR}]Traceback (most recent call last):[/{_C.ERROR}]")
        panel_content = colored_err
        
    if isinstance(panel_content, Syntax) and truncated:
        # We can't easily concat rich Syntax and Text, so we'll just put the truncated string in the panel subtitle
        subtitle = truncated.strip()
    else:
        panel_content = f"{panel_content}{truncated}" if isinstance(panel_content, str) else panel_content
        subtitle = None

    _console.print(
        Panel(
            panel_content,
            title=f"[{title_style}]{name}[/{title_style}]",
            title_align="left",
            subtitle=subtitle,
            border_style=border_style,
            padding=(0, 1),
        )
    )


# ---------------------------------------------------------------------------
# Stats line
# ---------------------------------------------------------------------------
def print_stats(stats: "TurnStats"):
    """Print a compact per-turn stats line."""
    if not _RICH:
        est = stats.prompt_tokens_est + stats.completion_tokens_est
        print(f"  ─ turn {stats.turn} │ ~{est} tokens │ {stats.elapsed_s:.1f}s ─")
        return

    # Build token display — prefer real counts if available
    prompt_tok = (
        stats.prompt_tokens_real
        if stats.prompt_tokens_real is not None
        else f"~{stats.prompt_tokens_est}"
    )
    compl_tok = (
        stats.completion_tokens_real
        if stats.completion_tokens_real is not None
        else f"~{stats.completion_tokens_est}"
    )

    # Context pressure bar
    pct = min(1.0, max(0.0, stats.context_budget_used))
    bar_len = 10
    filled = int(round(pct * bar_len))
    bar_str = "█" * filled + "░" * (bar_len - filled)
    
    if pct < 0.5:
        bar_color = _C.OK
    elif pct < 0.8:
        bar_color = _C.WARN
    else:
        bar_color = _C.ERROR
        
    context_part = f"[{bar_color}]{bar_str} {int(pct*100)}%[/{bar_color}]"

    parts = [
        f"[dim]turn {stats.turn}[/dim]",
        f"[{_C.BRAND}]{prompt_tok}[/{_C.BRAND}][dim] prompt[/dim]",
        f"[{_C.BRAND}]{compl_tok}[/{_C.BRAND}][dim] completion[/dim]",
        f"[{_C.BRAND}]{int(stats.tokens_per_sec)}[/{_C.BRAND}][dim] tok/s[/dim]",
        context_part,
        f"[dim]{stats.elapsed_s:.1f}s[/dim]",
    ]
    if stats.compaction_triggered:
        parts.append(f"[{_C.WARN}]⚡ compacted[/{_C.WARN}]")
        
    _console.print("  " + f"  [dim]│[/dim]  ".join(parts), markup=True)


def print_session_stats(stats: "SessionStats"):
    """Print the full session stats table (/stats command)."""
    if not _RICH:
        print(f"\n  Session Stats")
        print(f"  Turns:         {stats.total_turns}")
        print(f"  Prompt tok:    {stats.total_prompt_tokens}")
        print(f"  Completion tok:{stats.total_completion_tokens}")
        print(f"  Compactions:   {stats.compaction_count}")
        print(f"  Checkpoints:   {stats.checkpoint_count}\n")
        return

    table = Table(
        title="Session Statistics",
        box=box.ROUNDED,
        title_style=_C.HEADER,
        border_style=_C.BORDER,
        show_header=True,
        header_style=_C.DIM,
    )
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right", style="cyan")

    total_tok = stats.total_prompt_tokens + stats.total_completion_tokens
    table.add_row("Turns completed", str(stats.total_turns))
    table.add_row("Prompt tokens (est.)", str(stats.total_prompt_tokens))
    table.add_row("Completion tokens (est.)", str(stats.total_completion_tokens))
    table.add_row("Total tokens (est.)", str(total_tok))
    table.add_row("Context compactions", str(stats.compaction_count))
    table.add_row("Checkpoints saved", str(stats.checkpoint_count))
    _console.print(table)


# ---------------------------------------------------------------------------
# Special events
# ---------------------------------------------------------------------------
def print_event(kind: str, message: str):
    """Print a special event line (compaction, checkpoint, etc.)."""
    icons = {
        "compact":    ("⚡", _C.WARN),
        "checkpoint": ("📌", _C.OK),
        "session":    ("💾", _C.INFO),
        "warn":       ("⚠️",  _C.WARN),
        "error":      ("✖",  _C.ERROR),
        "ok":         ("✔",  _C.OK),
        "info":       ("ℹ",  _C.INFO),
    }
    icon, style = icons.get(kind, ("•", _C.DIM))

    if _RICH:
        _console.print(f"  [{style}]{icon}  {message}[/{style}]")
    else:
        print(f"  {icon}  {message}")


# ---------------------------------------------------------------------------
# Config table
# ---------------------------------------------------------------------------
def print_config_table(rows: list[tuple[str, str, str]]):
    """Print a config table.  rows = [(key, value, description), ...]"""
    if not _RICH:
        print("\n  Current configuration:")
        for key, val, desc in rows:
            print(f"    {key:<28} {val:<20} {desc}")
        print()
        return

    table = Table(
        title="Runtime Configuration",
        box=box.ROUNDED,
        title_style=_C.HEADER,
        border_style=_C.BORDER,
        show_header=True,
        header_style=_C.DIM,
    )
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold white", justify="right")
    table.add_column("Description", style="dim")

    for key, val, desc in rows:
        table.add_row(key, str(val), desc)

    _console.print(table)


# ---------------------------------------------------------------------------
# Session listing
# ---------------------------------------------------------------------------
def print_session_table(sessions: list[dict], current_name: str):
    """Print a table of saved sessions."""
    if not _RICH:
        print("\n  Sessions:")
        for s in sessions:
            marker = " ◀" if s["name"] == current_name else ""
            print(f"    {s['name']}  ({s['messages']} msgs, {s['skills']} skills){marker}")
        print()
        return

    import datetime
    table = Table(
        title="Saved Sessions",
        box=box.ROUNDED,
        title_style=_C.HEADER,
        border_style=_C.BORDER,
        show_header=True,
        header_style=_C.DIM,
    )
    table.add_column("Name", style="bold cyan")
    table.add_column("Messages", justify="right")
    table.add_column("Skills", justify="right")
    table.add_column("Last Updated", style="dim")
    table.add_column("", style="bold green")

    for s in sessions:
        ts = s.get("updated_at", 0)
        ts_str = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "—"
        marker = "◀ active" if s["name"] == current_name else ""
        table.add_row(
            s["name"],
            str(s["messages"]),
            str(s["skills"]),
            ts_str,
            marker,
        )
    _console.print(table)


# ---------------------------------------------------------------------------
# Skills listing
# ---------------------------------------------------------------------------
def print_skills_table(skills):
    """Print indexed skills."""
    if not _RICH:
        for s in skills:
            t = "🗂️" if s.skill_type == "hub" else "📖"
            print(f"    {t} {s.slug:30s} — {(s.description or '')[:60]}")
        return

    table = Table(
        title=f"Indexed Skills ({len(skills)})",
        box=box.ROUNDED,
        title_style=_C.HEADER,
        border_style=_C.BORDER,
        show_header=True,
        header_style=_C.DIM,
    )
    table.add_column("Type", justify="center", width=4)
    table.add_column("Slug", style="cyan")
    table.add_column("Tags", style="dim")
    table.add_column("Description", style="dim")

    for s in skills:
        t = "🗂️" if s.skill_type == "hub" else "📖"
        tags = ", ".join(s.tags) if s.tags else ""
        desc = (s.description or "")[:70]
        table.add_row(t, s.slug, tags, desc)
    _console.print(table)


# ---------------------------------------------------------------------------
# Health check output
# ---------------------------------------------------------------------------
def print_health(label: str, url: str, ok: bool):
    """Print a health check result line."""
    if ok:
        _p(f"  [green]✔[/green] [dim]{label}:[/dim] {url}")
    else:
        _p(f"  [yellow]⚠[/yellow] [dim]{label}:[/dim] [yellow]{url} not reachable[/yellow]")


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
def clear_screen():
    """Clear the terminal screen."""
    if _RICH:
        _console.clear()
    else:
        import os
        os.system("cls" if sys.platform == "win32" else "clear")


def print_separator():
    if _RICH:
        _console.rule(style=_C.BORDER)
    else:
        print("  " + "─" * 60)


# ---------------------------------------------------------------------------
# Guidance UI
# ---------------------------------------------------------------------------
def print_guidance(hints: list[tuple[str, str]]):
    """Print meta-guidance hints (level, message)."""
    if not hints:
        return
        
    for level, msg in hints:
        if level == "info":
            _p(f"  [dim]💡  {msg}[/dim]")
        elif level == "warn":
            _p(f"  [{_C.WARN}]⚡  {msg}[/{_C.WARN}]")
        elif level == "error":
            _p(f"  [{_C.ERROR}]⚠️  {msg}[/{_C.ERROR}]")


# ---------------------------------------------------------------------------
# Review UI
# ---------------------------------------------------------------------------
def run_review_session(log_manager) -> bool:
    """Run an interactive review session in the terminal. Returns True if ran."""
    unreviewed = log_manager.list_unreviewed()
    if not unreviewed:
        _p(f"  [{_C.OK}]✔  No unreviewed interactions.[/{_C.OK}]")
        return True

    html_path = log_manager.generate_html_report()
    _p(f"\n  [bold]📋  Unreviewed interactions: {len(unreviewed)}[/bold]")
    _p(f"  [dim]💡  A full HTML report is available at:[/dim] [{_C.INFO}]{html_path}[/{_C.INFO}]")
    _p(f"  [{_C.BORDER}]─────────────────────────────────────────[/{_C.BORDER}]")

    for i, entry in enumerate(unreviewed):
        idx = i + 1
        ts = entry.get("ts", "")[:16].replace("T", " ")
        user_input = entry.get("user_input", "")
        if len(user_input) > 40:
            user_input = user_input[:37] + "…"
        
        outcome = entry.get("outcome", "unknown")
        icon = f"[{_C.OK}]✅[/{_C.OK}]" if outcome == "success" else f"[{_C.ERROR}]❌[/{_C.ERROR}]"
        elapsed = entry.get("elapsed_s", 0.0)
        
        _p(f"  [dim][{idx}][/dim] {ts}  \"{user_input}\"   {icon} {outcome}  {elapsed:.1f}s")
        
    _p(f"  [{_C.BORDER}]─────────────────────────────────────────[/{_C.BORDER}]")
    
    while True:
        choice = input(f"  Review [1-{len(unreviewed)}/all/skip]? > ").strip().lower()
        if not choice or choice == "skip":
            break
            
        if choice == "all":
            to_review = unreviewed
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(unreviewed):
                    to_review = [unreviewed[idx]]
                else:
                    _p(f"  [{_C.WARN}]Invalid index.[/{_C.WARN}]")
                    continue
            except ValueError:
                break
                
        for entry in to_review:
            _p(f"\n  [{_C.BRAND}]--- Reviewing: {entry.get('ts')} ---[/{_C.BRAND}]")
            _p(f"  [bold]User:[/bold] {entry.get('user_input')}")
            for a in entry.get("actions", []):
                err_mark = f"[{_C.ERROR}](err)[/{_C.ERROR}]" if a.get("exit_code", 0) != 0 else ""
                _p(f"  [dim]↳ {a.get('name')} {a.get('body_preview', '')} {err_mark}[/dim]")
            
            rating = input("  Rating (good/bad/skip) [skip]: ").strip().lower()
            if rating in ("good", "bad", "g", "b", "+", "-"):
                r = "good" if rating in ("good", "g", "+") else "bad"
                notes = input("  Notes (optional): ").strip()
                log_manager.mark_reviewed(entry, rating=r, notes=notes)
                _p(f"  [{_C.OK}]Saved.[/{_C.OK}]")
            else:
                log_manager.mark_reviewed(entry, rating=None, notes="")
                _p(f"  [dim]Skipped rating, marked as reviewed.[/dim]")
        break
        
    return True

