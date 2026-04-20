"""Tests for embedding provider selection and requests."""

from unittest.mock import MagicMock, patch

import pytest

from src.errors import ConfigurationError, VectorStoreError


def test_embed_texts_openai_returns_vectors():
    with patch("src.llm.embeddings.settings") as mock_settings:
        mock_settings.embedding_provider = "openai"
        mock_settings.embedding_model = "text-embedding-3-small"
        mock_settings.openai_api_key = "sk-test"

        fake_item = MagicMock()
        fake_item.embedding = [0.1, 0.2]
        fake_response = MagicMock(data=[fake_item])
        fake_client = MagicMock()
        fake_client.embeddings.create.return_value = fake_response

        from src.llm.embeddings import EmbeddingClient

        client = EmbeddingClient(openai_client=fake_client)
        vectors = client.embed_texts(["hello"])

        assert vectors == [[0.1, 0.2]]
        fake_client.embeddings.create.assert_called_once_with(
            input=["hello"],
            model="text-embedding-3-small",
        )


def test_embed_texts_openai_requires_api_key():
    with patch("src.llm.embeddings.settings") as mock_settings:
        mock_settings.embedding_provider = "openai"
        mock_settings.embedding_model = "text-embedding-3-small"
        mock_settings.openai_api_key = ""

        from src.llm.embeddings import EmbeddingClient

        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
            EmbeddingClient().embed_texts(["hello"])


def test_embed_texts_ollama_returns_vectors():
    with patch("src.llm.embeddings.settings") as mock_settings:
        mock_settings.embedding_provider = "ollama"
        mock_settings.embedding_model = "nomic-embed-text"
        mock_settings.embedding_base_url = "http://localhost:11434"

        http_client = MagicMock()
        http_client.post.return_value.json.return_value = {
            "embeddings": [[0.1, 0.2], [0.3, 0.4]]
        }
        http_client.post.return_value.raise_for_status.return_value = None

        from src.llm.embeddings import EmbeddingClient

        client = EmbeddingClient(http_client=http_client)
        vectors = client.embed_texts(["hello", "world"])

        assert vectors == [[0.1, 0.2], [0.3, 0.4]]
        http_client.post.assert_called_once_with(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": ["hello", "world"]},
            timeout=30.0,
        )


def test_embed_texts_ollama_wraps_request_errors():
    with patch("src.llm.embeddings.settings") as mock_settings:
        mock_settings.embedding_provider = "ollama"
        mock_settings.embedding_model = "nomic-embed-text"
        mock_settings.embedding_base_url = "http://localhost:11434"

        http_client = MagicMock()
        http_client.post.side_effect = RuntimeError("connection refused")

        from src.llm.embeddings import EmbeddingClient

        with pytest.raises(VectorStoreError, match="connection refused"):
            EmbeddingClient(http_client=http_client).embed_texts(["hello"])


def test_embed_texts_unknown_provider_raises_configuration_error():
    with patch("src.llm.embeddings.settings") as mock_settings:
        mock_settings.embedding_provider = "wat"

        from src.llm.embeddings import EmbeddingClient

        with pytest.raises(ConfigurationError, match="Unknown EMBEDDING_PROVIDER"):
            EmbeddingClient().embed_texts(["hello"])
