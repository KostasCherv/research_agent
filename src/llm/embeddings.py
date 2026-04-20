"""Embedding provider abstraction for vector-store operations."""

from __future__ import annotations

import httpx

from src.config import settings
from src.errors import ConfigurationError, VectorStoreError


class EmbeddingClient:
    """Embed text batches using the configured provider."""

    def __init__(self, openai_client: object | None = None, http_client: object | None = None) -> None:
        self._openai_client = openai_client
        self._http_client = http_client or httpx.Client()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return vectors for *texts* using the configured embedding provider."""
        provider = settings.embedding_provider.lower()

        if provider == "openai":
            return self._embed_with_openai(texts)
        if provider == "ollama":
            return self._embed_with_ollama(texts)

        raise ConfigurationError(
            f"Unknown EMBEDDING_PROVIDER '{provider}'. Choose 'openai' or 'ollama'."
        )

    def _embed_with_openai(self, texts: list[str]) -> list[list[float]]:
        if not settings.openai_api_key:
            raise ConfigurationError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai.")

        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=settings.openai_api_key)

        try:
            response = self._openai_client.embeddings.create(
                input=texts,
                model=settings.embedding_model,
            )
        except Exception as exc:
            raise VectorStoreError(f"Embedding request failed: {exc}") from exc

        return [item.embedding for item in response.data]

    def _embed_with_ollama(self, texts: list[str]) -> list[list[float]]:
        base_url = settings.embedding_base_url.rstrip("/")
        if not base_url:
            raise ConfigurationError(
                "EMBEDDING_BASE_URL is required when EMBEDDING_PROVIDER=ollama."
            )

        try:
            response = self._http_client.post(
                f"{base_url}/api/embed",
                json={"model": settings.embedding_model, "input": texts},
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise VectorStoreError(f"Embedding request failed: {exc}") from exc

        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise VectorStoreError("Embedding request failed: Ollama response missing embeddings.")
        return embeddings
