"""Tests for src/tools/vector_store.py"""

from unittest.mock import MagicMock
import pytest

from src.errors import VectorStoreError


def _make_manager():
    from src.tools.vector_store import VectorStoreManager
    return VectorStoreManager()


def _make_manager_with_mocks():
    """Return (manager, mock_index, mock_openai_client) with embeddings pre-configured."""
    manager = _make_manager()

    mock_index = MagicMock()
    manager._index = mock_index

    mock_openai = MagicMock()
    fake_embedding = MagicMock()
    fake_embedding.embedding = [0.1] * 1536
    mock_embed_response = MagicMock()
    mock_embed_response.data = [fake_embedding]
    mock_openai.embeddings.create.return_value = mock_embed_response
    manager._openai_client = mock_openai

    return manager, mock_index, mock_openai


# ---------------------------------------------------------------------------
# save_report / search_reports
# ---------------------------------------------------------------------------

def test_save_report_calls_index_upsert():
    manager, mock_index, _ = _make_manager_with_mocks()

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
    manager, mock_index, _ = _make_manager_with_mocks()
    mock_index.upsert.side_effect = RuntimeError("pinecone down")

    with pytest.raises(VectorStoreError, match="pinecone down"):
        manager.save_report(query="test", report="# Report")


def test_search_reports_returns_structured_list():
    manager, mock_index, _ = _make_manager_with_mocks()
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
    manager, mock_index, _ = _make_manager_with_mocks()
    mock_index.query.side_effect = RuntimeError("query failed")

    with pytest.raises(VectorStoreError, match="query failed"):
        manager.search_reports("anything")


# ---------------------------------------------------------------------------
# save_source_chunks / search_run_sources
# ---------------------------------------------------------------------------

def test_save_source_chunks_calls_upsert():
    manager, mock_index, _ = _make_manager_with_mocks()
    # Return enough fake embeddings for all chunks
    fake_embedding = MagicMock()
    fake_embedding.embedding = [0.1] * 1536
    manager._openai_client.embeddings.create.return_value = MagicMock(
        data=[fake_embedding, fake_embedding]
    )

    sources = [
        {"url": "https://a.com", "title": "A", "raw_text": "Some content about topic A."},
        {"url": "https://b.com", "title": "B", "raw_text": "Content about topic B."},
    ]
    count = manager.save_source_chunks(run_id="run-1", session_id="sess-1", sources=sources)

    assert count > 0
    mock_index.upsert.assert_called()
    # Check the first upsert batch
    call_kwargs = mock_index.upsert.call_args.kwargs
    assert call_kwargs["namespace"] == "source_chunks"
    vectors = call_kwargs["vectors"]
    assert len(vectors) == count
    for v in vectors:
        assert v["metadata"]["run_id"] == "run-1"
        assert v["metadata"]["session_id"] == "sess-1"
        assert "text" in v["metadata"]


def test_save_source_chunks_returns_zero_for_empty_sources():
    manager, mock_index, _ = _make_manager_with_mocks()
    count = manager.save_source_chunks(run_id="run-1", session_id="sess-1", sources=[])
    assert count == 0
    mock_index.upsert.assert_not_called()


def test_search_run_sources_returns_structured_list():
    manager, mock_index, _ = _make_manager_with_mocks()
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

    # Ensure run_id filter is applied
    call_kwargs = mock_index.query.call_args.kwargs
    assert call_kwargs["filter"] == {"run_id": {"$eq": "run-1"}}
    assert call_kwargs["namespace"] == "source_chunks"


def test_search_run_sources_returns_empty_when_no_chunks():
    manager, mock_index, _ = _make_manager_with_mocks()
    mock_index.query.return_value = MagicMock(matches=[])

    results = manager.search_run_sources("query text", run_id="run-1")

    assert results == []
    # Pinecone always queries — it returns empty matches, no short-circuit
    mock_index.query.assert_called_once()


def test_search_run_sources_raises_on_failure():
    manager, mock_index, _ = _make_manager_with_mocks()
    mock_index.query.side_effect = RuntimeError("query error")

    with pytest.raises(VectorStoreError, match="query error"):
        manager.search_run_sources("anything", run_id="run-1")
