"""ChromaDB vector store manager."""

import logging
from datetime import datetime, UTC

from src.config import settings
from src.errors import VectorStoreError

logger = logging.getLogger(__name__)


from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from chromadb import ClientAPI, Collection

class VectorStoreManager:
    """Thin wrapper around ChromaDB for storing and querying research reports."""

    COLLECTION_NAME = "research_reports"

    def __init__(self, persist_directory: str | None = None) -> None:
        self._persist_dir = persist_directory or settings.chroma_persist_directory
        self._client: Optional["ClientAPI"] = None
        self._collection: Optional["Collection"] = None

    def _ensure_client(self):
        if self._client is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

    def save_report(self, query: str, report: str, metadata: dict | None = None) -> str:
        """Persist a research report to Chroma.

        Args:
            query: The original research query (used as document ID seed).
            report: Markdown report text.
            metadata: Optional extra metadata dict.

        Returns:
            The document ID used for storage.

        Raises:
            VectorStoreError: On any Chroma error.
        """
        try:
            self._ensure_client()
            doc_id = f"report_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
            meta = {
                "query": query[:512],
                "generated_at": datetime.now(UTC).isoformat(),
                **(metadata or {}),
            }
            if self._collection is None:
                raise VectorStoreError("Collection not initialized.")
            self._collection.add(
                documents=[report],
                metadatas=[meta],
                ids=[doc_id],
            )
            logger.info("Saved report '%s' to vector store.", doc_id)
            return doc_id
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
            VectorStoreError: On any Chroma error.
        """
        try:
            self._ensure_client()
            if self._collection is None:
                raise VectorStoreError("Collection not initialized.")
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
            )
            output = []
            for i, doc_id in enumerate(results["ids"][0]):
                output.append({
                    "id": doc_id,
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                })
            return output
        except Exception as exc:
            raise VectorStoreError(f"Failed to search reports: {exc}") from exc
