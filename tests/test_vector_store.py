"""Tests for src/tools/vector_store.py"""

from unittest.mock import MagicMock, patch

import pytest

from src.errors import VectorStoreError


def _make_manager():
    from src.tools.vector_store import VectorStoreManager

    return VectorStoreManager()


def _make_manager_with_mocks():
    """Return (manager, mock_index, mock_pinecone_client, mock_embedding_client)."""
    manager = _make_manager()

    mock_index = MagicMock()
    mock_pinecone = MagicMock()
    mock_index_info = MagicMock()
    mock_index_info.dimension = 1536
    mock_pinecone.describe_index.return_value = mock_index_info

    manager._index = mock_index
    manager._pinecone_client = mock_pinecone
    manager._embedding_client = MagicMock()
    manager._embedding_client.embed_texts.return_value = [[0.1] * 1536]

    return manager, mock_index, mock_pinecone, manager._embedding_client


def test_save_report_calls_index_upsert():
    manager, mock_index, _, _ = _make_manager_with_mocks()

    doc_id = manager.save_report(query="LangGraph", report="# Report")

    mock_index.upsert.assert_called_once()
    call_kwargs = mock_index.upsert.call_args.kwargs
    vectors = call_kwargs["vectors"]
    assert len(vectors) == 1
    assert vectors[0]["id"].startswith("report_")
    assert vectors[0]["metadata"]["query"] == "LangGraph"
    assert vectors[0]["metadata"]["document"] == "# Report"
    assert call_kwargs["namespace"] == "reports"
    assert doc_id.startswith("report_")


def test_save_report_raises_vector_store_error_on_failure():
    manager, mock_index, _, _ = _make_manager_with_mocks()
    mock_index.upsert.side_effect = RuntimeError("pinecone down")

    with pytest.raises(VectorStoreError, match="pinecone down"):
        manager.save_report(query="test", report="# Report")


def test_search_reports_returns_structured_list():
    manager, mock_index, _, _ = _make_manager_with_mocks()
    mock_match = MagicMock()
    mock_match.id = "report_001"
    mock_match.metadata = {
        "query": "LangGraph",
        "generated_at": "2026-01-01",
        "document": "# Report content",
    }
    mock_index.query.return_value = MagicMock(matches=[mock_match])

    results = manager.search_reports("LangGraph")

    assert len(results) == 1
    assert results[0]["id"] == "report_001"
    assert results[0]["document"] == "# Report content"
    assert results[0]["metadata"]["query"] == "LangGraph"


def test_search_reports_raises_on_failure():
    manager, mock_index, _, _ = _make_manager_with_mocks()
    mock_index.query.side_effect = RuntimeError("query failed")

    with pytest.raises(VectorStoreError, match="query failed"):
        manager.search_reports("anything")


def test_save_source_chunks_calls_upsert():
    manager, mock_index, _, mock_embedding_client = _make_manager_with_mocks()
    mock_embedding_client.embed_texts.return_value = [[0.1] * 1536, [0.1] * 1536]

    sources = [
        {"url": "https://a.com", "title": "A", "raw_text": "Some content about topic A."},
        {"url": "https://b.com", "title": "B", "raw_text": "Content about topic B."},
    ]
    count = manager.save_source_chunks(run_id="run-1", session_id="sess-1", sources=sources)

    assert count > 0
    mock_index.upsert.assert_called()
    call_kwargs = mock_index.upsert.call_args.kwargs
    assert call_kwargs["namespace"] == "source_chunks"
    vectors = call_kwargs["vectors"]
    assert len(vectors) == count
    for v in vectors:
        assert v["metadata"]["run_id"] == "run-1"
        assert v["metadata"]["session_id"] == "sess-1"
        assert "text" in v["metadata"]


def test_save_source_chunks_returns_zero_for_empty_sources():
    manager, mock_index, _, _ = _make_manager_with_mocks()
    count = manager.save_source_chunks(run_id="run-1", session_id="sess-1", sources=[])
    assert count == 0
    mock_index.upsert.assert_not_called()


def test_search_run_sources_returns_structured_list():
    manager, mock_index, _, _ = _make_manager_with_mocks()
    mock_match = MagicMock()
    mock_match.metadata = {
        "run_id": "run-1",
        "session_id": "sess-1",
        "source_url": "https://a.com",
        "source_title": "A",
        "chunk_index": 0,
        "text": "Relevant text here.",
    }
    mock_index.query.return_value = MagicMock(matches=[mock_match])

    results = manager.search_run_sources("query text", run_id="run-1")

    assert len(results) == 1
    assert results[0]["text"] == "Relevant text here."
    assert results[0]["source_url"] == "https://a.com"
    assert results[0]["source_title"] == "A"

    call_kwargs = mock_index.query.call_args.kwargs
    assert call_kwargs["filter"] == {"run_id": {"$eq": "run-1"}}
    assert call_kwargs["namespace"] == "source_chunks"


def test_search_run_sources_returns_empty_when_no_chunks():
    manager, mock_index, _, _ = _make_manager_with_mocks()
    mock_index.query.return_value = MagicMock(matches=[])

    results = manager.search_run_sources("query text", run_id="run-1")

    assert results == []
    mock_index.query.assert_called_once()


def test_search_run_sources_raises_on_failure():
    manager, mock_index, _, _ = _make_manager_with_mocks()
    mock_index.query.side_effect = RuntimeError("query error")

    with pytest.raises(VectorStoreError, match="query error"):
        manager.search_run_sources("anything", run_id="run-1")


def test_dimension_mismatch_raises_clear_error():
    manager, _, mock_pinecone, _ = _make_manager_with_mocks()
    mock_index_info = MagicMock()
    mock_index_info.dimension = 768
    mock_pinecone.describe_index.return_value = mock_index_info

    with patch("src.tools.vector_store.settings") as mock_settings:
        mock_settings.pinecone_index_name = "research-agent-ollama-nomic"
        mock_settings.embedding_dimensions = 1536
        with pytest.raises(VectorStoreError, match="does not match the configured embedding dimensions"):
            manager.save_report(query="LangGraph", report="# Report")
