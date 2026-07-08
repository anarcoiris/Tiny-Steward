"""Unit tests for the HelpEngine and semantic skill retrieval.

Tests skill discovery, cosine similarity matching, and formatting constraints.
"""

from __future__ import annotations

import unittest
from pathlib import Path
import numpy as np

from core.skill_loader import Skill, SkillIndex
from core.help import HelpEngine


class MockEmbedder:
    """Mock embedder that returns pre-defined vectors for testing."""

    def __init__(self, vocabulary: dict[str, list[float]]):
        self.vocabulary = vocabulary
        # Fallback random vector
        self.fallback = [0.1] * 768

    def embed(self, text: str) -> np.ndarray:
        for keyword, vector in self.vocabulary.items():
            if keyword.lower() in text.lower():
                return np.array(vector, dtype=np.float32)
        return np.array(self.fallback, dtype=np.float32)


class TestHelpEngine(unittest.TestCase):
    """Test suite for semantic capability search."""

    def setUp(self):
        # Create some mock skills
        self.skills = [
            Skill(
                name="Git Clone",
                slug="git_clone",
                path="skills/git/clone.md",
                skill_type="skill",
                tags=["git", "repository", "source-control"],
                related=["ssh_keys", "github_auth"],
                description="Clone a remote repository to a local directory.",
                body="Clone a repository with git clone <url>.",
            ),
            Skill(
                name="SSH Keys",
                slug="ssh_keys",
                path="skills/git/ssh_keys.md",
                skill_type="skill",
                tags=["ssh", "keys", "authentication", "permission-denied"],
                related=["github_auth"],
                description="Generate, configure, and troubleshoot SSH keys.",
                body="Generate a key using ssh-keygen.",
            ),
            Skill(
                name="Docker Hub",
                slug="docker",
                path="skills/docker/docker.md",
                skill_type="hub",
                tags=["docker", "containers", "deployment"],
                children=["docker_compose", "docker_logs"],
                description="Container management hub.",
                body="Welcome to the Docker hub.",
            ),
            Skill(
                name="Docker Compose",
                slug="docker_compose",
                path="skills/docker/compose.md",
                skill_type="skill",
                tags=["docker", "compose", "multi-container"],
                description="Define and run multi-container applications.",
                body="Run docker compose up.",
            ),
        ]

        # Let's define some 4-dimensional vectors for mock embedding math
        # Git-related query vector matches git/ssh skills
        # Docker-related query vector matches docker skills
        self.vectors = np.array([
            [1.0, 0.0, 0.0, 0.0],  # git_clone
            [0.8, 0.2, 0.0, 0.0],  # ssh_keys
            [0.0, 0.0, 1.0, 0.0],  # docker hub
            [0.0, 0.0, 0.8, 0.2],  # docker_compose
        ], dtype=np.float32)

        # Pad vectors to 768 dimensions to simulate Nomic embeddings
        padded_vectors = np.zeros((len(self.skills), 768), dtype=np.float32)
        padded_vectors[:, :4] = self.vectors
        self.index = SkillIndex(self.skills, padded_vectors)

        # Mock vocabulary maps keywords to padded 768-d vectors
        v_git = [1.0, 0.1, 0.0, 0.0] + [0.0] * 764
        v_docker = [0.0, 0.0, 1.0, 0.1] + [0.0] * 764
        self.vocab = {
            "git": v_git,
            "clone": v_git,
            "ssh": v_git,
            "docker": v_docker,
            "container": v_docker,
        }
        self.embedder = MockEmbedder(self.vocab)
        self.help_engine = HelpEngine(
            self.index,
            self.embedder,
            top_k=2,
            min_similarity=0.3,
            max_inject_tokens=1000,
        )

    def test_exact_slug_search(self):
        """Test retrieving a specific skill by its slug."""
        result = self.help_engine.search_exact("git_clone")
        self.assertIn("Git Clone", result)
        self.assertIn("git clone <url>", result)

    def test_semantic_search_git(self):
        """Test query for 'git clone' matches git skills."""
        result = self.help_engine.search("git clone")
        self.assertIn("Git Clone", result)
        self.assertIn("SSH Keys", result)
        self.assertNotIn("Docker Hub", result)

    def test_semantic_search_docker(self):
        """Test query for 'docker containers' matches docker skills."""
        result = self.help_engine.search("docker containers")
        self.assertIn("Docker Hub", result)
        self.assertIn("Docker Compose", result)
        self.assertNotIn("Git Clone", result)

    def test_hub_format(self):
        """Test that hub skills output child lists instead of full bodies."""
        result = self.help_engine.search("docker")
        self.assertIn("🗂️ Docker Hub", result)
        self.assertIn("Available sub-skills", result)
        self.assertIn("- `docker_compose`", result)


if __name__ == "__main__":
    unittest.main()
