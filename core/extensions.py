"""Extension, Skill & MCP Tool Inspection and Management Module for Tiny-Steward.

Provides unified discovery, health verification, and inspection for:
- Skills (markdown packages under skills/)
- MCP Tools (Model Context Protocol servers like nina-mcp, chronos_mcp)
- Custom Python Plugins
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.skill_loader import discover_skills, load_skill, Skill


class ExtensionManager:
    """Discovers, inspects, and manages Tiny-Steward extensions, skills, and tools."""

    def __init__(self, workspace_root: Path | str | None = None, config: dict[str, Any] | None = None):
        self.workspace_root = Path(workspace_root or ".").resolve()
        self.skills_dir = self.workspace_root / "skills"
        self.config = config or {}

    def get_skills(self) -> list[dict[str, Any]]:
        """Discover and list all available skills in skills/ directory."""
        if not self.skills_dir.exists():
            return []

        parsed_skills = discover_skills(self.skills_dir)
        skills_summary = []
        for s in parsed_skills:
            skills_summary.append({
                "name": s.name,
                "slug": s.slug,
                "type": s.skill_type,
                "path": s.path,
                "description": s.description,
                "tags": s.tags,
                "requires": s.requires,
                "provides": s.provides,
            })
        return skills_summary

    def get_mcp_tools(self) -> list[dict[str, Any]]:
        """Inspect active MCP tools and server configs."""
        mcp_cfg = self.config.get("mcp", {})
        mcp_tools = []

        # Check nina-mcp launcher
        python_exe = mcp_cfg.get("python_exe", "")
        client_py = mcp_cfg.get("client_py", "")
        if client_py and Path(client_py).exists():
            mcp_tools.append({
                "server": "nina-mcp",
                "status": "configured",
                "client_py": client_py,
                "python_exe": python_exe,
                "description": "NINA Smart Scheduler & Astronomical Observatory MCP Server",
            })

        # Check skills/chronos_mcp
        chronos_dir = self.skills_dir / "chronos_mcp"
        if chronos_dir.exists():
            mcp_tools.append({
                "server": "chronos-mcp",
                "status": "installed",
                "path": str(chronos_dir),
                "description": "Chronos MCP Timekeeping & Scheduler Extension",
            })

        return mcp_tools

    def get_all_extensions(self) -> dict[str, Any]:
        """Return full extension summary including skills, MCP tools, and workspace status."""
        skills = self.get_skills()
        mcp_tools = self.get_mcp_tools()

        return {
            "workspace": str(self.workspace_root),
            "total_skills": len(skills),
            "total_mcp_servers": len(mcp_tools),
            "skills": skills,
            "mcp_tools": mcp_tools,
        }
