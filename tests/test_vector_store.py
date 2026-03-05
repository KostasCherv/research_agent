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
