"""help() — the semantic capability router.

Embeds a query, searches the skill index, and returns formatted
skill documents for injection into the conversation.

This is the core abstraction: instead of loading all tools into context,
the agent discovers capabilities on demand via embedding search.
"""

from __future__ import annotations

from core.embedder import Embedder, cosine_similarity
from core.skill_loader import SkillIndex, Skill
from core.llm import estimate_tokens


class HelpEngine:
    """Semantic search over the skill graph."""

    def __init__(
        self,
        index: SkillIndex,
        embedder: Embedder,
        top_k: int = 5,
        min_similarity: float = 0.35,
        max_inject_tokens: int = 4000,
    ):
        self.index = index
        self.embedder = embedder
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.max_inject_tokens = max_inject_tokens

    def search(self, query: str) -> str:
        """Search for skills relevant to a query.

        Returns formatted markdown text ready for injection
        into the conversation as a system/tool message.
        """
        if self.index.vectors is None or self.index.size == 0:
            return "_No skills indexed. Run --build-index first._"

        # 1. Embed the query
        q_vec = self.embedder.embed(query)

        # 2. Cosine similarity against all skills
        scores = cosine_similarity(q_vec, self.index.vectors)

        # 3. Top-k, filtered by min similarity
        ranked = sorted(enumerate(scores), key=lambda x: -x[1])
        top = [
            (i, float(s))
            for i, s in ranked[:self.top_k]
            if float(s) >= self.min_similarity
        ]

        if not top:
            return (
                f"_No skills found matching \"{query}\" "
                f"(best score: {float(ranked[0][1]):.2f} < threshold {self.min_similarity})._"
            )

        # 4. Build response with budget tracking
        sections: list[str] = []
        token_budget = self.max_inject_tokens
        related_slugs: set[str] = set()

        for idx, score in top:
            skill = self.index.skills[idx]

            # For hub skills: show TOC only (children list)
            if skill.skill_type == "hub":
                content = self._format_hub(skill, score)
            else:
                content = self._format_skill(skill, score)

            content_tokens = estimate_tokens(content)
            if content_tokens > token_budget:
                # Try a summary instead
                summary = self._format_summary(skill, score)
                if estimate_tokens(summary) <= token_budget:
                    sections.append(summary)
                    token_budget -= estimate_tokens(summary)
                break

            sections.append(content)
            token_budget -= content_tokens

            # Collect related skills for hints
            for slug in skill.related:
                if slug not in {s.slug for s in self.index.skills}:
                    continue
                related_slugs.add(slug)

        # 5. Append brief related hints if budget allows
        # Remove skills already shown
        shown_slugs = {self.index.skills[i].slug for i, _ in top}
        related_slugs -= shown_slugs

        if related_slugs and token_budget > 200:
            hints = self._format_related_hints(related_slugs)
            if estimate_tokens(hints) <= token_budget:
                sections.append(hints)

        return "\n\n---\n\n".join(sections)

    def search_exact(self, slug: str) -> str:
        """Load a specific skill by slug (for follow-up requests)."""
        skill = self.index.get_by_slug(slug)
        if not skill:
            return f"_Skill '{slug}' not found in index._"
        return self._format_skill(skill, score=1.0)

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------
    def _format_skill(self, skill: Skill, score: float) -> str:
        """Full skill content for injection."""
        header = f"## 📖 {skill.name} (relevance: {score:.2f})"
        meta_parts = []
        if skill.requires:
            meta_parts.append(f"**requires**: {', '.join(skill.requires)}")
        if skill.provides:
            meta_parts.append(f"**provides**: {', '.join(skill.provides)}")
        if skill.related:
            meta_parts.append(f"**related**: {', '.join(skill.related)}")

        meta = " · ".join(meta_parts) if meta_parts else ""
        body = skill.body if skill.body else "_No detailed documentation._"

        parts = [header]
        if meta:
            parts.append(f"_{meta}_")
        parts.append(body)
        return "\n\n".join(parts)

    def _format_hub(self, skill: Skill, score: float) -> str:
        """Hub skill: table of contents only."""
        header = f"## 🗂️ {skill.name} (hub, relevance: {score:.2f})"
        body = skill.body if skill.body else ""

        children_section = ""
        if skill.children:
            children_section = "\n**Available sub-skills** (use `help(\"<name>\")` to load):\n"
            for child in skill.children:
                child_skill = self.index.get_by_slug(child)
                if child_skill:
                    children_section += f"- `{child}` — {child_skill.description or child_skill.name}\n"
                else:
                    children_section += f"- `{child}`\n"

        return "\n\n".join(filter(None, [header, body, children_section]))

    def _format_summary(self, skill: Skill, score: float) -> str:
        """Brief summary when budget is tight."""
        desc = skill.description or skill.name
        return f"- **{skill.name}** ({score:.2f}): {desc}"

    def _format_related_hints(self, slugs: set[str]) -> str:
        """Brief hints about related skills."""
        lines = ["### Related skills (use `help(\"<name>\")` to expand):"]
        for slug in sorted(slugs):
            skill = self.index.get_by_slug(slug)
            if skill:
                lines.append(f"- `{slug}` — {skill.description or skill.name}")
            else:
                lines.append(f"- `{slug}`")
        return "\n".join(lines)
