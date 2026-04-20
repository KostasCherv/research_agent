"""Pinecone vector store manager."""

import hashlib
import logging
from datetime import datetime, UTC
from typing import Optional

from src.config import settings
from src.errors import VectorStoreError
from src.llm.embeddings import EmbeddingClient

logger = logging.getLogger(__name__)

# Characters per chunk when splitting source text for run-scoped retrieval
_CHUNK_SIZE = 1000
# Max texts per embedding API call
_EMBED_BATCH_SIZE = 500
# Pinecone namespaces
_NAMESPACE_REPORTS = "reports"
_NAMESPACE_CHUNKS = "source_chunks"
# Pinecone metadata value size limit (bytes); truncate document text to stay under 40KB
_META_TEXT_LIMIT = 38_000


class VectorStoreManager:
    """Thin wrapper around Pinecone for storing and querying research reports."""

    def __init__(self) -> None:
        self._index: Optional[object] = None
        self._pinecone_client: Optional[object] = None
        self._embedding_client: Optional[EmbeddingClient] = None
        self._index_dimension_validated = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_index(self):
        """Return a connected Pinecone index, initialising lazily."""
        if self._index is not None:
            return self._index
        if not settings.pinecone_api_key:
            raise VectorStoreError(
                "PINECONE_API_KEY is not set. "
                "Add it to your .env file before using the vector store."
            )
        from pinecone import Pinecone

        pc = Pinecone(api_key=settings.pinecone_api_key)
        self._pinecone_client = pc
        self._index = pc.Index(settings.pinecone_index_name)
        return self._index

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for *texts* using the configured provider."""
        if self._embedding_client is None:
            self._embedding_client = EmbeddingClient()

        embeddings: list[list[float]] = []
        for batch_start in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[batch_start : batch_start + _EMBED_BATCH_SIZE]
            try:
                embeddings.extend(self._embedding_client.embed_texts(batch))
            except VectorStoreError:
                raise
            except Exception as exc:
                raise VectorStoreError(f"Embedding request failed: {exc}") from exc
        return embeddings

    def _extract_index_dimension(self, index_info: object) -> int | None:
        """Best-effort extraction of a Pinecone index dimension from SDK responses."""
        if hasattr(index_info, "dimension"):
            dimension = getattr(index_info, "dimension")
            if isinstance(dimension, int):
                return dimension

        if isinstance(index_info, dict):
            dimension = index_info.get("dimension")
            if isinstance(dimension, int):
                return dimension

        return None

    def _validate_index_dimension(self) -> None:
        """Ensure the configured Pinecone index matches the embedding dimensions."""
        if self._index_dimension_validated:
            return

        self._ensure_index()
        if self._pinecone_client is None:
            raise VectorStoreError("Pinecone client is not initialized.")

        try:
            index_info = self._pinecone_client.describe_index(settings.pinecone_index_name)
        except Exception as exc:
            raise VectorStoreError(f"Failed to inspect Pinecone index: {exc}") from exc

        index_dimension = self._extract_index_dimension(index_info)
        if index_dimension is None:
            raise VectorStoreError(
                "Failed to inspect Pinecone index: index dimension was not available."
            )

        if index_dimension != settings.embedding_dimensions:
            raise VectorStoreError(
                "Pinecone index "
                f"'{settings.pinecone_index_name}' dimension {index_dimension} does not match "
                f"the configured embedding dimensions {settings.embedding_dimensions}. "
                "Use a matching index or reindex existing data for this embedding model."
            )

        self._index_dimension_validated = True

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def save_report(self, query: str, report: str, metadata: dict | None = None) -> str:
        """Persist a research report to Pinecone.

        Args:
            query: The original research query.
            report: Markdown report text.
            metadata: Optional extra metadata dict.

        Returns:
            The document ID used for storage.

        Raises:
            VectorStoreError: On any Pinecone or embedding error.
        """
        try:
            self._validate_index_dimension()
            doc_id = f"report_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
            doc_text = report[:_META_TEXT_LIMIT]
            if len(report) > _META_TEXT_LIMIT:
                logger.warning(
                    "[vector_store] report truncated from %d to %d chars for metadata storage.",
                    len(report),
                    _META_TEXT_LIMIT,
                )
            meta = {
                "query": query[:512],
                "generated_at": datetime.now(UTC).isoformat(),
                "document": doc_text,
                **(metadata or {}),
            }
            embedding = self._embed([report])
            self._ensure_index().upsert(
                vectors=[{"id": doc_id, "values": embedding[0], "metadata": meta}],
                namespace=_NAMESPACE_REPORTS,
            )
            logger.info("Saved report '%s' to vector store.", doc_id)
            return doc_id
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(f"Failed to save report: {exc}") from exc

    def search_reports(self, query: str, n_results: int = 3) -> list[dict]:
        """Semantic search over stored reports.

        Args:
            query: Natural language query.
            n_results: Number of results to return.

        Returns:
            List of dicts with ``id``, ``document``, and ``metadata`` keys.

        Raises:
            VectorStoreError: On any Pinecone or embedding error.
        """
        try:
            self._validate_index_dimension()
            embedding = self._embed([query])
            response = self._ensure_index().query(
                vector=embedding[0],
                top_k=n_results,
                namespace=_NAMESPACE_REPORTS,
                include_metadata=True,
            )
            return [
                {
                    "id": match.id,
                    "document": (match.metadata or {}).get("document", ""),
                    "metadata": match.metadata or {},
                }
                for match in response.matches
            ]
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(f"Failed to search reports: {exc}") from exc

    # ---------------------------------------------------------------------------
    # Run-scoped source chunks (for session follow-up retrieval)
    # ---------------------------------------------------------------------------

    def save_source_chunks(
        self,
        run_id: str,
        session_id: str,
        sources: list[dict],
    ) -> int:
        """Split and persist source texts as chunks keyed to a run.

        Each source dict may have ``url``, ``title``, and ``raw_text`` or
        ``summary`` fields.

        Args:
            run_id: Unique ID for this research run.
            session_id: Parent session ID.
            sources: List of source dicts from ``retrieved_contents`` or
                ``summaries``.

        Returns:
            Number of chunks saved.
        """
        try:
            self._validate_index_dimension()
            ids: list[str] = []
            texts: list[str] = []
            metadatas: list[dict] = []

            for source in sources:
                text: str = source.get("raw_text") or source.get("summary", "")
                url: str = source.get("url", "")
                title: str = source.get("title", "")

                chunks = [
                    text[start : start + _CHUNK_SIZE]
                    for start in range(0, max(len(text), 1), _CHUNK_SIZE)
                    if text[start : start + _CHUNK_SIZE].strip()
                ]
                for chunk_index, chunk_text in enumerate(chunks):
                    id_seed = f"{run_id}:{url}:{chunk_index}"
                    chunk_id = hashlib.md5(id_seed.encode()).hexdigest()
                    ids.append(chunk_id)
                    texts.append(chunk_text)
                    metadatas.append(
                        {
                            "run_id": run_id,
                            "session_id": session_id,
                            "source_url": url[:512],
                            "source_title": title[:256],
                            "chunk_index": chunk_index,
                            "text": chunk_text,
                        }
                    )

            if not ids:
                return 0

            embeddings = self._embed(texts)
            index = self._ensure_index()

            for batch_start in range(0, len(ids), _EMBED_BATCH_SIZE):
                batch_end = batch_start + _EMBED_BATCH_SIZE
                vectors = [
                    {
                        "id": ids[i],
                        "values": embeddings[i],
                        "metadata": metadatas[i],
                    }
                    for i in range(batch_start, min(batch_end, len(ids)))
                ]
                index.upsert(vectors=vectors, namespace=_NAMESPACE_CHUNKS)

            logger.info("[vector_store] saved %d chunks for run %s", len(ids), run_id)
            return len(ids)
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(f"Failed to save source chunks: {exc}") from exc

    def search_run_sources(
        self,
        query: str,
        run_id: str,
        n_results: int = 5,
    ) -> list[dict]:
        """Semantic search over source chunks scoped to a specific run.

        Args:
            query: Natural language question.
            run_id: Limits results to chunks from this run.
            n_results: Max results to return.

        Returns:
            List of dicts with ``text``, ``source_url``, ``source_title``,
            ``chunk_index`` keys.
        """
        try:
            self._validate_index_dimension()
            embedding = self._embed([query])
            response = self._ensure_index().query(
                vector=embedding[0],
                top_k=n_results,
                namespace=_NAMESPACE_CHUNKS,
                include_metadata=True,
                filter={"run_id": {"$eq": run_id}},
            )
            if not response.matches:
                return []
            return [
                {
                    "text": (match.metadata or {}).get("text", ""),
                    "source_url": (match.metadata or {}).get("source_url", ""),
                    "source_title": (match.metadata or {}).get("source_title", ""),
                    "chunk_index": (match.metadata or {}).get("chunk_index", 0),
                }
                for match in response.matches
            ]
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(f"Failed to search run sources: {exc}") from exc
