"""Unit tests for Multi-Provider LLM architecture and resilient fallback mechanism."""

import pytest
import os
from unittest.mock import MagicMock, patch

from core.providers.llm_provider import (
    LlamaCppProvider,
    OllamaProvider,
    GitHubModelsProvider,
    OpenRouterProvider,
    GroqProvider,
    GeminiProvider,
    create_provider_from_config,
)
from core.llm import LLMClient, merge_reasoning_into_content


def test_provider_initialization():
    gh = GitHubModelsProvider(api_key="test_token")
    assert gh.provider_type == "github"
    assert gh.api_key == "test_token"
    assert "models.github.ai" in gh.base_url

    openrouter = OpenRouterProvider(api_key="test_or")
    assert openrouter.provider_type == "openrouter"
    assert openrouter.api_key == "test_or"

    groq = GroqProvider(api_key="test_groq")
    assert groq.provider_type == "groq"
    assert groq.api_key == "test_groq"

    gemini = GeminiProvider(api_key="test_gemini")
    assert gemini.provider_type == "gemini"
    assert gemini.api_key == "test_gemini"

    ollama = OllamaProvider()
    assert ollama.provider_type == "ollama"

    llama = LlamaCppProvider("local", "http://127.0.0.1:11440", "qwythos-9b")
    assert llama.provider_type == "llamacpp"


def test_create_provider_from_config():
    cfg = {
        "provider": "github",
        "base_url": "https://models.github.ai/inference",
        "model": "openai/gpt-4o",
        "api_key": "dummy_key",
    }
    p = create_provider_from_config("test_gh", cfg)
    assert isinstance(p, GitHubModelsProvider)
    assert p.model == "openai/gpt-4o"
    assert p.api_key == "dummy_key"


def test_llm_client_fallback_trigger():
    # Setup mock fallback provider
    mock_fallback = MagicMock()
    mock_fallback.name = "github_models"
    mock_fallback.model = "openai/gpt-4o"
    mock_fallback.chat.return_value = "<think>\nFalling back to GitHub Models\n</think>\n\nFallback response content"

    client = LLMClient(
        base_url="http://127.0.0.1:99999",  # unreachable primary port
        model="dummy_local",
        fallback_providers=[mock_fallback],
    )

    messages = [{"role": "user", "content": "Hello"}]
    
    # Primary call will fail due to connection error; fallback should be triggered!
    res = client.chat(messages)

    assert "Fallback response content" in res
    assert client.active_provider_name == "github_models"
    mock_fallback.chat.assert_called_once_with(messages, max_tokens=None, temperature=None, tools=None)
