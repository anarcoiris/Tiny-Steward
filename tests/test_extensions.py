"""Unit tests for ExtensionManager and skill/tool inspection."""

import pytest
from pathlib import Path
from core.extensions import ExtensionManager


def test_extension_manager_discovery(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create dummy skill
    skill_file = skills_dir / "test_skill.md"
    skill_file.write_text(
        "---\n"
        "name: Test Skill\n"
        "slug: test-skill\n"
        "tags: [test, automation]\n"
        "---\n"
        "# Test Skill Body\n"
        "This is a test skill description paragraph.\n",
        encoding="utf-8"
    )

    config = {
        "mcp": {
            "client_py": str(tmp_path / "dummy_client.py")
        }
    }
    (tmp_path / "dummy_client.py").write_text("# dummy", encoding="utf-8")

    mgr = ExtensionManager(workspace_root=tmp_path, config=config)
    skills = mgr.get_skills()

    assert len(skills) == 1
    assert skills[0]["name"] == "Test Skill"
    assert skills[0]["slug"] == "test-skill"

    mcp_tools = mgr.get_mcp_tools()
    assert len(mcp_tools) == 1
    assert mcp_tools[0]["server"] == "nina-mcp"
