"""Skill loader — parses the skills/ directory into a searchable index.

Each skill is a Markdown file with YAML frontmatter containing:
  name, requires, provides, tags, related, type

The loader:
1. Walks the skills/ tree
2. Parses frontmatter + body
3. Generates an embedding for each skill (name + tags + first paragraph)
4. Saves the index to _index.json (metadata) + _vectors.npy (embeddings)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml


@dataclass
class Skill:
    """A parsed skill from the skills/ directory."""

    name: str
    slug: str
    path: str                           # relative to skills root
    skill_type: str = "skill"           # skill | hub | agent
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)  # for hub type
    description: str = ""               # first paragraph
    body: str = ""                      # full markdown body (no frontmatter)
    system_prompt: str = ""             # custom system prompt for agents


    @property
    def embed_text(self) -> str:
        """Text used for embedding generation."""
        parts = [self.name]
        if self.tags:
            parts.append(" ".join(self.tags))
        if self.description:
            parts.append(self.description)
        return " — ".join(parts)


def parse_frontmatter(content: str, filepath: Path | None = None) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from a markdown file.

    Returns (frontmatter_dict, body_text).
    Handles --- delimited frontmatter.
    """
    # Match --- at start of file
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not match:
        return {}, content

    fm_text = match.group(1)
    body = match.group(2)

    try:
        fm = yaml.safe_load(fm_text)
        if not isinstance(fm, dict):
            fm = {}
    except Exception as e:
        context = f" in {filepath}" if filepath else ""
        print(f"  [warn] Failed to parse frontmatter YAML{context}: {e}")
        fm = {}

    return fm, body


def extract_first_paragraph(body: str) -> str:
    """Extract the first non-heading, non-empty paragraph from markdown."""
    lines = body.strip().split("\n")
    paragraph_lines: list[str] = []
    in_paragraph = False

    for line in lines:
        stripped = line.strip()
        # Skip headings and empty lines before first paragraph
        if stripped.startswith("#") or stripped.startswith("---"):
            if in_paragraph:
                break
            continue
        if not stripped:
            if in_paragraph:
                break
            continue
        in_paragraph = True
        paragraph_lines.append(stripped)

    return " ".join(paragraph_lines)


def load_skill(filepath: Path, skills_root: Path) -> Skill:
    """Load a single skill from a markdown file."""
    content = filepath.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content, filepath)

    name = fm.get("name", filepath.stem)
    slug = fm.get("slug", filepath.stem)
    rel_path = str(filepath.relative_to(skills_root)).replace("\\", "/")

    return Skill(
        name=name,
        slug=slug,
        path=rel_path,
        skill_type=fm.get("type", "skill"),
        requires=[str(x) for x in fm.get("requires", [])] if isinstance(fm.get("requires"), list) else [],
        provides=[str(x) for x in fm.get("provides", [])] if isinstance(fm.get("provides"), list) else [],
        tags=[str(x) for x in fm.get("tags", [])] if isinstance(fm.get("tags"), list) else [],
        related=[str(x) for x in fm.get("related", [])] if isinstance(fm.get("related"), list) else [],
        children=[str(x) for x in fm.get("children", [])] if isinstance(fm.get("children"), list) else [],
        description=extract_first_paragraph(body),
        body=body.strip(),
        system_prompt=str(fm.get("system_prompt", "")) if fm.get("system_prompt") is not None else "",
    )


# OpenClaw contamination under skills/_meta — exclude from semantic index.
# Keep on disk; still index _meta/primitives and _meta/troubleshooting.
OPENCLAW_META_EXCLUDE = frozenset({
    "delegation-gate",
    "delegate-router",
    "pulse-routing",
    "nomic-local",
    "paid-bash-security-v1-1",
})


def discover_skills(skills_root: Path) -> list[Skill]:
    """Walk the skills/ directory and parse all .md files.

    Foreign OpenClaw packs under ``_meta/<name>/`` listed in
    :data:`OPENCLAW_META_EXCLUDE` are kept on disk but not indexed.
    ``_meta/primitives`` and ``_meta/troubleshooting`` remain discoverable.
    """
    skills: list[Skill] = []
    for md_file in sorted(skills_root.rglob("*.md")):
        # Skip index/readme/claude files
        if md_file.name.startswith("_") or md_file.name.lower() in ("readme.md", "claude.md"):
            continue
        try:
            rel_parts = md_file.relative_to(skills_root).parts
        except ValueError:
            continue
        if (
            len(rel_parts) >= 2
            and rel_parts[0] == "_meta"
            and rel_parts[1] in OPENCLAW_META_EXCLUDE
        ):
            continue
        try:
            skill = load_skill(md_file, skills_root)
            skills.append(skill)
        except Exception as e:
            print(f"  [warn] Failed to parse {md_file}: {e}")
    return skills


class SkillIndex:
    """In-memory index of skills with embedding vectors for search."""

    def __init__(self, skills: list[Skill], vectors: np.ndarray | None = None):
        self.skills = skills
        self.vectors = vectors  # shape: (n_skills, embed_dim)
        self._slug_map = {s.slug: i for i, s in enumerate(skills)}
        self._name_map = {s.name.lower(): i for i, s in enumerate(skills)}

    def get_by_slug(self, slug: str) -> Skill | None:
        idx = self._slug_map.get(slug)
        return self.skills[idx] if idx is not None else None

    def get_by_name(self, name: str) -> Skill | None:
        idx = self._name_map.get(name.lower())
        return self.skills[idx] if idx is not None else None

    @property
    def size(self) -> int:
        return len(self.skills)

    def save(self, index_path: Path):
        """Save index metadata to JSON and vectors to .npy."""
        # Metadata (without body to keep JSON small)
        meta = []
        for s in self.skills:
            d = asdict(s)
            d.pop("body", None)  # don't store full body in index
            meta.append(d)

        index_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Vectors
        if self.vectors is not None:
            vec_path = index_path.with_suffix(".npy")
            np.save(str(vec_path), self.vectors)

    @classmethod
    def load(cls, index_path: Path, skills_root: Path) -> SkillIndex:
        """Load a previously saved index."""
        meta = json.loads(index_path.read_text(encoding="utf-8"))
        vec_path = index_path.with_suffix(".npy")

        # Reconstruct skills with bodies from disk
        skills: list[Skill] = []
        for entry in meta:
            full_path = skills_root / entry["path"]
            if full_path.exists():
                skill = load_skill(full_path, skills_root)
            else:
                # Fallback: use metadata without body
                skill = Skill(**{k: v for k, v in entry.items() if k in Skill.__dataclass_fields__})
            skills.append(skill)

        vectors = None
        if vec_path.exists():
            vectors = np.load(str(vec_path))

        return cls(skills, vectors)


def build_index(skills_root: Path, embedder) -> SkillIndex:
    """Discover all skills, generate embeddings, return a SkillIndex.

    Args:
        skills_root: Path to skills/ directory
        embedder: Embedder instance for generating vectors
    """
    print(f"  Discovering skills in {skills_root} ...")
    skills = discover_skills(skills_root)
    print(f"  Found {len(skills)} skills")

    if not skills:
        return SkillIndex(skills, None)

    print("  Generating embeddings ...")
    texts = [s.embed_text for s in skills]
    vectors = embedder.embed_batch(texts)
    print(f"  Index built: {vectors.shape}")

    return SkillIndex(skills, vectors)
