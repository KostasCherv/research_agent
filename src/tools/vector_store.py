"""ChromaDB vector store manager."""

import hashlib
import logging
from datetime import datetime, UTC

from src.config import settings
from src.errors import VectorStoreError

logger = logging.getLogger(__name__)


from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from chromadb import ClientAPI, Collection

# Characters per chunk when splitting source text for run-scoped retrieval
_CHUNK_SIZE = 1000


class VectorStoreManager:
    """Thin wrapper around ChromaDB for storing and querying research reports."""

    COLLECTION_NAME = "research_reports"
    CHUNKS_COLLECTION_NAME = "source_chunks"

    def __init__(self, persist_directory: str | None = None) -> None:
        self._persist_dir = persist_directory or settings.chroma_persist_directory
        self._client: Optional["ClientAPI"] = None
        self._collection: Optional["Collection"] = None
        self._chunks_collection: Optional["Collection"] = None

    def _ensure_client(self):
        if self._client is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

    def _ensure_chunks_collection(self) -> "Collection":
        """Return the source_chunks collection, initialising it if needed."""
        if self._chunks_collection is None:
            if self._client is None:
                import chromadb
                self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._chunks_collection = self._client.get_or_create_collection(
                name=self.CHUNKS_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._chunks_collection

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
            collection = self._ensure_chunks_collection()
            ids: list[str] = []
            documents: list[str] = []
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
                    # Stable, collision-resistant ID
                    id_seed = f"{run_id}:{url}:{chunk_index}"
                    chunk_id = hashlib.md5(id_seed.encode()).hexdigest()
                    ids.append(chunk_id)
                    documents.append(chunk_text)
                    metadatas.append(
                        {
                            "run_id": run_id,
                            "session_id": session_id,
                            "source_url": url[:512],
                            "source_title": title[:256],
                            "chunk_index": chunk_index,
                        }
                    )

            if ids:
                collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
            logger.info("[vector_store] saved %d chunks for run %s", len(ids), run_id)
            return len(ids)
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
            collection = self._ensure_chunks_collection()
            # Guard: Chroma raises if the collection is empty or n_results > count
            count = collection.count()
            if count == 0:
                return []
            effective_n = min(n_results, count)
            results = collection.query(
                query_texts=[query],
                n_results=effective_n,
                where={"run_id": run_id},
            )
            output: list[dict] = []
            for i, _ in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]
                output.append(
                    {
                        "text": results["documents"][0][i],
                        "source_url": meta.get("source_url", ""),
                        "source_title": meta.get("source_title", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                    }
                )
            return output
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(f"Failed to search run sources: {exc}") from exc
