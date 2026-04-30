"""Tests for the compiled LangGraph (src/graph/graph.py)"""

import asyncio
from unittest.mock import patch, MagicMock
from unittest.mock import AsyncMock


def _make_mock_nodes():
    """Return a dict of no-op node mocks that pass state through."""
    def passthrough(state):
        return state

    return passthrough


def test_build_graph_returns_compiled_graph():
    from src.graph.graph import build_graph

    graph = build_graph()
    # A compiled LangGraph has an .invoke method
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "stream")


def test_graph_invoke_with_error_reaches_abort(monkeypatch):
    from src.errors import SearchError

    with patch("src.graph.nodes.perform_search", side_effect=SearchError("no search")):
        from src.graph.graph import build_graph
        graph = build_graph()

        # Patch LLM to ensure we don't need real API keys
        final = asyncio.run(
            graph.ainvoke({"query": "test", "use_vector_store": False, "error": None})
        )

    # Pipeline should abort and set an error
    assert final.get("error") is not None


def test_graph_invoke_happy_path(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            MagicMock(
                content='[{"url":"https://example.com","title":"Example","summary":"Source summary."}]'
            ),
            MagicMock(content="Combined insights."),
            MagicMock(content="# Report\nFinal output."),
        ]
    )

    search_result = [{"url": "https://example.com", "title": "Example", "content": "Content"}]

    with (
        patch("src.graph.nodes.perform_search", return_value=search_result),
        patch("src.graph.nodes.fetch_url_content", new=AsyncMock(return_value="Fetched page text")),
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.graph.nodes.VectorStoreManager"),
    ):
        from src.graph.graph import build_graph
        graph = build_graph()
        final = asyncio.run(
            graph.ainvoke({"query": "LangGraph", "use_vector_store": False, "error": None})
        )

    assert "report" in final
    assert len(final["report"]) > 0


def test_graph_invoke_continues_when_memory_lookup_fails():
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            MagicMock(
                content='[{"url":"https://example.com","title":"Example","summary":"Source summary."}]'
            ),
            MagicMock(content="Combined insights."),
            MagicMock(content="# Report\nFinal output."),
        ]
    )

    search_result = [{"url": "https://example.com", "title": "Example", "content": "Content"}]

    with (
        patch("src.graph.nodes.perform_search", return_value=search_result),
        patch("src.graph.nodes.fetch_url_content", new=AsyncMock(return_value="Fetched page text")),
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.graph.nodes.VectorStoreManager") as mock_vs_cls,
    ):
        mock_vs = MagicMock()
        mock_vs.search_reports.side_effect = RuntimeError("chroma unavailable")
        mock_vs_cls.return_value = mock_vs

        from src.graph.graph import build_graph
        graph = build_graph()
        final = asyncio.run(
            graph.ainvoke({"query": "LangGraph", "use_vector_store": False, "error": None})
        )

    assert "report" in final
    assert len(final["report"]) > 0
