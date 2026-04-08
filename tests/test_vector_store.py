"""Tests for src/tools/vector_store.py"""

from unittest.mock import MagicMock, patch
import pytest

from src.errors import VectorStoreError


def _make_manager():
    from src.tools.vector_store import VectorStoreManager
    return VectorStoreManager(persist_directory="/tmp/test_chroma")


def test_save_report_calls_collection_add():
    manager = _make_manager()
    mock_collection = MagicMock()
    manager._client = MagicMock()
    manager._collection = mock_collection

    doc_id = manager.save_report(query="LangGraph", report="# Report")

    mock_collection.add.assert_called_once()
    call_kwargs = mock_collection.add.call_args.kwargs
    assert call_kwargs["documents"] == ["# Report"]
    assert call_kwargs["metadatas"][0]["query"] == "LangGraph"
    assert doc_id.startswith("report_")


def test_save_report_raises_vector_store_error_on_failure():
    manager = _make_manager()
    manager._client = MagicMock()
    manager._collection = MagicMock()
    manager._collection.add.side_effect = RuntimeError("chroma down")

    with pytest.raises(VectorStoreError, match="chroma down"):
        manager.save_report(query="test", report="# Report")


def test_search_reports_returns_structured_list():
    manager = _make_manager()
    manager._client = MagicMock()
    manager._collection = MagicMock()
    manager._collection.query.return_value = {
        "ids": [["report_001"]],
        "documents": [["# Report content"]],
        "metadatas": [[{"query": "LangGraph", "generated_at": "2026-01-01"}]],
    }

    results = manager.search_reports("LangGraph")

    assert len(results) == 1
    assert results[0]["id"] == "report_001"
    assert results[0]["document"] == "# Report content"
    assert results[0]["metadata"]["query"] == "LangGraph"


def test_search_reports_raises_on_failure():
    manager = _make_manager()
    manager._client = MagicMock()
    manager._collection = MagicMock()
    manager._collection.query.side_effect = RuntimeError("query failed")

    with pytest.raises(VectorStoreError, match="query failed"):
        manager.search_reports("anything")


# ---------------------------------------------------------------------------
# save_source_chunks / search_run_sources
# ---------------------------------------------------------------------------

def _make_manager_with_chunks_collection():
    manager = _make_manager()
    manager._client = MagicMock()
    manager._collection = MagicMock()
    mock_chunks = MagicMock()
    manager._chunks_collection = mock_chunks
    return manager, mock_chunks


def test_save_source_chunks_calls_upsert():
    manager, mock_chunks = _make_manager_with_chunks_collection()
    sources = [
        {"url": "https://a.com", "title": "A", "raw_text": "Some content about topic A."},
        {"url": "https://b.com", "title": "B", "raw_text": "Content about topic B."},
    ]
    count = manager.save_source_chunks(
        run_id="run-1",
        session_id="sess-1",
        sources=sources,
    )
    assert count > 0
    mock_chunks.upsert.assert_called_once()
    call_kwargs = mock_chunks.upsert.call_args.kwargs
    assert len(call_kwargs["documents"]) == count
    for meta in call_kwargs["metadatas"]:
        assert meta["run_id"] == "run-1"
        assert meta["session_id"] == "sess-1"


def test_save_source_chunks_returns_zero_for_empty_sources():
    manager, mock_chunks = _make_manager_with_chunks_collection()
    count = manager.save_source_chunks(run_id="run-1", session_id="sess-1", sources=[])
    assert count == 0
    mock_chunks.upsert.assert_not_called()


def test_search_run_sources_returns_structured_list():
    manager, mock_chunks = _make_manager_with_chunks_collection()
    mock_chunks.count.return_value = 3
    mock_chunks.query.return_value = {
        "ids": [["chunk_001"]],
        "documents": [["Relevant text here."]],
        "metadatas": [[{
            "run_id": "run-1",
            "session_id": "sess-1",
            "source_url": "https://a.com",
            "source_title": "A",
            "chunk_index": 0,
        }]],
    }

    results = manager.search_run_sources("query text", run_id="run-1")

    assert len(results) == 1
    assert results[0]["text"] == "Relevant text here."
    assert results[0]["source_url"] == "https://a.com"
    assert results[0]["source_title"] == "A"

    # Ensure where filter is applied
    call_kwargs = mock_chunks.query.call_args.kwargs
    assert call_kwargs["where"] == {"run_id": "run-1"}


def test_search_run_sources_returns_empty_when_no_chunks():
    manager, mock_chunks = _make_manager_with_chunks_collection()
    mock_chunks.count.return_value = 0

    results = manager.search_run_sources("query text", run_id="run-1")
    assert results == []
    mock_chunks.query.assert_not_called()


def test_search_run_sources_raises_on_failure():
    manager, mock_chunks = _make_manager_with_chunks_collection()
    mock_chunks.count.return_value = 5
    mock_chunks.query.side_effect = RuntimeError("query error")

    with pytest.raises(VectorStoreError, match="query error"):
        manager.search_run_sources("anything", run_id="run-1")
