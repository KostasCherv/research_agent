"""Tests for graph nodes (src/graph/nodes.py)"""

import asyncio
from unittest.mock import patch, MagicMock
from unittest.mock import AsyncMock


# ---------------------------------------------------------------------------
# search_node
# ---------------------------------------------------------------------------

def test_search_node_populates_results():
    with patch("src.graph.nodes.perform_search") as mock_search:
        mock_search.return_value = [{"url": "https://a.com", "title": "A", "content": "..."}]
        from src.graph.nodes import search_node
        state = asyncio.run(search_node({"query": "LangGraph", "error": None}))

    assert state["error"] is None
    assert len(state["search_results"]) == 1


def test_search_node_sets_error_on_failure():
    from src.errors import SearchError
    with patch("src.graph.nodes.perform_search", side_effect=SearchError("boom")):
        from src.graph.nodes import search_node
        state = asyncio.run(search_node({"query": "fail", "error": None}))

    assert state["error"] == "boom"
    assert state["search_results"] == []


# ---------------------------------------------------------------------------
# retrieve_node
# ---------------------------------------------------------------------------

def test_retrieve_node_fetches_content():
    with patch("src.graph.nodes.fetch_url_content", new=AsyncMock(return_value="fetched text")):
        from src.graph.nodes import retrieve_node
        state = asyncio.run(retrieve_node({
            "query": "test",
            "search_results": [{"url": "https://a.com", "title": "A", "content": "snippet"}],
        }))

    assert len(state["retrieved_contents"]) == 1
    assert state["retrieved_contents"][0]["raw_text"] == "fetched text"


def test_retrieve_node_falls_back_to_snippet_on_failure():
    from src.errors import FetchError

    with patch("src.graph.nodes.fetch_url_content", new=AsyncMock(side_effect=FetchError("no route"))):
        from src.graph.nodes import retrieve_node
        state = asyncio.run(retrieve_node({
            "query": "test",
            "search_results": [{"url": "https://a.com", "title": "A", "content": "snippet text"}],
        }))

    assert state["retrieved_contents"][0]["raw_text"] == "snippet text"


# ---------------------------------------------------------------------------
# summarize_node
# ---------------------------------------------------------------------------

def test_summarize_node_calls_llm():
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Nice summary."))

    with patch("src.graph.nodes.get_llm", return_value=mock_llm):
        from src.graph.nodes import summarize_node
        state = asyncio.run(summarize_node({
            "query": "LangGraph",
            "retrieved_contents": [{"url": "https://a.com", "title": "A", "raw_text": "Some text content here."}],
        }))

    assert len(state["summaries"]) == 1
    assert state["summaries"][0]["summary"] == "Nice summary."


# ---------------------------------------------------------------------------
# combine_node
# ---------------------------------------------------------------------------

def test_combine_node_merges_summaries():
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Combined insights."))

    with patch("src.graph.nodes.get_llm", return_value=mock_llm):
        from src.graph.nodes import combine_node
        state = asyncio.run(combine_node({
            "query": "LangGraph",
            "summaries": [{"url": "https://a.com", "title": "A", "summary": "Summary A"}],
        }))

    assert state["combined_insights"] == "Combined insights."


# ---------------------------------------------------------------------------
# report_node
# ---------------------------------------------------------------------------

def test_report_node_generates_report():
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="# My Report\nContent here."))

    with patch("src.graph.nodes.get_llm", return_value=mock_llm):
        from src.graph.nodes import report_node
        state = asyncio.run(report_node({
            "query": "LangGraph",
            "combined_insights": "Insights text",
            "summaries": [{"url": "https://a.com", "title": "A", "summary": "x"}],
        }))

    assert "# My Report" in state["report"]
    assert "report_metadata" in state
    assert state["report_metadata"]["title"] == "LangGraph"


# ---------------------------------------------------------------------------
# vector_store_node
# ---------------------------------------------------------------------------

def test_vector_store_node_skips_when_disabled():
    from src.graph.nodes import vector_store_node
    state = asyncio.run(vector_store_node({"query": "test", "use_vector_store": False, "report": "# R"}))
    # Should pass through unchanged (no VectorStoreManager call)
    assert state["query"] == "test"


def test_vector_store_node_saves_when_enabled():
    with patch("src.graph.nodes.VectorStoreManager") as mock_cls:
        mock_manager = MagicMock()
        mock_manager.save_report.return_value = "report_001"
        mock_cls.return_value = mock_manager

        from src.graph.nodes import vector_store_node
        asyncio.run(
            vector_store_node({
                "query": "LangGraph",
                "use_vector_store": True,
                "report": "# Report",
                "report_metadata": {"title": "LangGraph"},
            })
        )

    mock_manager.save_report.assert_called_once()


# ---------------------------------------------------------------------------
# memory_context_node
# ---------------------------------------------------------------------------


def test_memory_context_node_builds_truncated_context():
    with patch("src.graph.nodes.VectorStoreManager") as mock_cls:
        mock_manager = MagicMock()
        long_doc = "A" * 2500
        mock_manager.search_reports.return_value = [
            {"id": "report_1", "document": long_doc, "metadata": {}},
            {"id": "report_2", "document": "Second doc", "metadata": {}},
        ]
        mock_cls.return_value = mock_manager

        from src.graph.nodes import memory_context_node
        state = asyncio.run(memory_context_node({"query": "LangGraph"}))

    assert "memory_context" in state
    assert state["memory_context"].startswith("A")
    assert len(state["memory_context"]) == 2000


def test_memory_context_node_returns_empty_context_when_no_results():
    with patch("src.graph.nodes.VectorStoreManager") as mock_cls:
        mock_manager = MagicMock()
        mock_manager.search_reports.return_value = []
        mock_cls.return_value = mock_manager

        from src.graph.nodes import memory_context_node
        state = asyncio.run(memory_context_node({"query": "LangGraph"}))

    assert state["memory_context"] == ""


def test_memory_context_node_handles_lookup_failure():
    with patch("src.graph.nodes.VectorStoreManager") as mock_cls:
        mock_manager = MagicMock()
        mock_manager.search_reports.side_effect = RuntimeError("chroma unavailable")
        mock_cls.return_value = mock_manager

        from src.graph.nodes import memory_context_node
        state = asyncio.run(memory_context_node({"query": "LangGraph"}))

    assert state["memory_context"] == ""
