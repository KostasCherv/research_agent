"""Tests for graph nodes (src/graph/nodes.py)"""

from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# search_node
# ---------------------------------------------------------------------------

def test_search_node_populates_results():
    with patch("src.graph.nodes.perform_search") as mock_search:
        mock_search.return_value = [{"url": "https://a.com", "title": "A", "content": "..."}]
        from src.graph.nodes import search_node
        state = search_node({"query": "LangGraph", "error": None})

    assert state["error"] is None
    assert len(state["search_results"]) == 1


def test_search_node_sets_error_on_failure():
    from src.errors import SearchError
    with patch("src.graph.nodes.perform_search", side_effect=SearchError("boom")):
        from src.graph.nodes import search_node
        state = search_node({"query": "fail", "error": None})

    assert state["error"] == "boom"
    assert state["search_results"] == []


# ---------------------------------------------------------------------------
# retrieve_node
# ---------------------------------------------------------------------------

def test_retrieve_node_fetches_content():
    def mock_asyncio_run(coro):
        coro.close()  # prevent "coroutine never awaited" warning
        return "fetched text"

    with patch("src.graph.nodes.asyncio.run", side_effect=mock_asyncio_run):
        from src.graph.nodes import retrieve_node
        state = retrieve_node({
            "query": "test",
            "search_results": [{"url": "https://a.com", "title": "A", "content": "snippet"}],
        })

    assert len(state["retrieved_contents"]) == 1
    assert state["retrieved_contents"][0]["raw_text"] == "fetched text"


def test_retrieve_node_falls_back_to_snippet_on_failure():
    from src.errors import FetchError

    def mock_asyncio_run(coro):
        coro.close()  # prevent "coroutine never awaited" warning
        raise FetchError("no route")

    with patch("src.graph.nodes.asyncio.run", side_effect=mock_asyncio_run):
        from src.graph.nodes import retrieve_node
        state = retrieve_node({
            "query": "test",
            "search_results": [{"url": "https://a.com", "title": "A", "content": "snippet text"}],
        })

    assert state["retrieved_contents"][0]["raw_text"] == "snippet text"


# ---------------------------------------------------------------------------
# summarize_node
# ---------------------------------------------------------------------------

def test_summarize_node_calls_llm():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Nice summary.")

    with patch("src.graph.nodes.get_llm", return_value=mock_llm):
        from src.graph.nodes import summarize_node
        state = summarize_node({
            "query": "LangGraph",
            "retrieved_contents": [{"url": "https://a.com", "title": "A", "raw_text": "Some text content here."}],
        })

    assert len(state["summaries"]) == 1
    assert state["summaries"][0]["summary"] == "Nice summary."


# ---------------------------------------------------------------------------
# combine_node
# ---------------------------------------------------------------------------

def test_combine_node_merges_summaries():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Combined insights.")

    with patch("src.graph.nodes.get_llm", return_value=mock_llm):
        from src.graph.nodes import combine_node
        state = combine_node({
            "query": "LangGraph",
            "summaries": [{"url": "https://a.com", "title": "A", "summary": "Summary A"}],
        })

    assert state["combined_insights"] == "Combined insights."


# ---------------------------------------------------------------------------
# report_node
# ---------------------------------------------------------------------------

def test_report_node_generates_report():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="# My Report\nContent here.")

    with (
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.config.settings.enable_structured_report_v2", False),
    ):
        from src.graph.nodes import report_node
        state = report_node({
            "query": "LangGraph",
            "combined_insights": "Insights text",
            "summaries": [{"url": "https://a.com", "title": "A", "summary": "x"}],
        })

    assert "# My Report" in state["report"]
    assert "report_metadata" in state
    assert state["report_metadata"]["title"] == "LangGraph"


# ---------------------------------------------------------------------------
# vector_store_node
# ---------------------------------------------------------------------------

def test_vector_store_node_skips_when_disabled():
    from src.graph.nodes import vector_store_node
    state = vector_store_node({"query": "test", "use_vector_store": False, "report": "# R"})
    # Should pass through unchanged (no VectorStoreManager call)
    assert state["query"] == "test"


def test_vector_store_node_saves_when_enabled():
    with patch("src.graph.nodes.VectorStoreManager") as mock_cls:
        mock_manager = MagicMock()
        mock_manager.save_report.return_value = "report_001"
        mock_cls.return_value = mock_manager

        from src.graph.nodes import vector_store_node
        state = vector_store_node({
            "query": "LangGraph",
            "use_vector_store": True,
            "report": "# Report",
            "report_metadata": {"title": "LangGraph"},
        })

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
        state = memory_context_node({"query": "LangGraph"})

    assert "memory_context" in state
    assert state["memory_context"].startswith("A")
    assert len(state["memory_context"]) == 2000


def test_memory_context_node_returns_empty_context_when_no_results():
    with patch("src.graph.nodes.VectorStoreManager") as mock_cls:
        mock_manager = MagicMock()
        mock_manager.search_reports.return_value = []
        mock_cls.return_value = mock_manager

        from src.graph.nodes import memory_context_node
        state = memory_context_node({"query": "LangGraph"})

    assert state["memory_context"] == ""


def test_memory_context_node_handles_lookup_failure():
    with patch("src.graph.nodes.VectorStoreManager") as mock_cls:
        mock_manager = MagicMock()
        mock_manager.search_reports.side_effect = RuntimeError("chroma unavailable")
        mock_cls.return_value = mock_manager

        from src.graph.nodes import memory_context_node
        state = memory_context_node({"query": "LangGraph"})

    assert state["memory_context"] == ""


# ---------------------------------------------------------------------------
# report_node — structured output v2
# ---------------------------------------------------------------------------

def _make_structured_report():
    from src.llm.output_parsers import StructuredReportV2, Claim, SourceAssessment
    return StructuredReportV2(
        title="LangGraph Report",
        executive_summary="LangGraph is a library for building stateful LLM applications.",
        claims=[
            Claim(
                id="claim-1",
                text="LangGraph supports stateful multi-agent workflows.",
                confidence=0.9,
                evidence_source_urls=["https://example.com"],
                evidence_quote="LangGraph enables stateful agents.",
            ),
            Claim(
                id="claim-2",
                text="LangGraph has limited community adoption.",
                confidence=0.3,
                evidence_source_urls=["https://example2.com"],
                evidence_quote="",
            ),
        ],
        conclusion="LangGraph is a promising but evolving framework.",
        source_assessments=[
            SourceAssessment(
                url="https://example.com",
                reliability_score=0.8,
                bias_flags=[],
                freshness_days=30,
            )
        ],
    )


def test_report_node_v2_returns_structured_report():
    structured = _make_structured_report()
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    mock_structured_llm.invoke.return_value = structured
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with (
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.config.settings.enable_structured_report_v2", True),
    ):
        from src.graph.nodes import report_node
        state = report_node({
            "query": "LangGraph",
            "combined_insights": "LangGraph synthesis text.",
            "summaries": [{"url": "https://example.com", "title": "Example", "summary": "x"}],
        })

    assert "structured_report" in state
    assert state["structured_report"]["title"] == "LangGraph Report"
    assert len(state["claims"]) == 2
    assert state["claims"][0]["confidence"] == 0.9
    assert len(state["source_assessments"]) == 1
    assert "report" in state
    assert "⚠️ Low confidence" in state["report"]  # claim-2 is low confidence


def test_report_node_v2_confidence_range():
    structured = _make_structured_report()
    for claim in structured.claims:
        assert 0.0 <= claim.confidence <= 1.0
    for sa in structured.source_assessments:
        assert 0.0 <= sa.reliability_score <= 1.0


def test_report_node_v2_retry_on_first_failure():
    structured = _make_structured_report()
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    # First call raises, second succeeds
    mock_structured_llm.invoke.side_effect = [RuntimeError("parse error"), structured]
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with (
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.config.settings.enable_structured_report_v2", True),
    ):
        from src.graph.nodes import report_node
        state = report_node({
            "query": "LangGraph",
            "combined_insights": "text",
            "summaries": [],
        })

    assert "structured_report" in state
    assert mock_structured_llm.invoke.call_count == 2


def test_report_node_v2_error_after_two_failures():
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    mock_structured_llm.invoke.side_effect = RuntimeError("always fails")
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with (
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.config.settings.enable_structured_report_v2", True),
    ):
        from src.graph.nodes import report_node
        state = report_node({
            "query": "LangGraph",
            "combined_insights": "text",
            "summaries": [],
        })

    assert state.get("error") is not None
    assert "structured output" in state["error"]
    assert mock_structured_llm.invoke.call_count == 2


def test_report_node_v1_fallback_when_flag_disabled():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="# Prose Report\nContent.")

    with (
        patch("src.graph.nodes.get_llm", return_value=mock_llm),
        patch("src.config.settings.enable_structured_report_v2", False),
    ):
        from src.graph.nodes import report_node
        state = report_node({
            "query": "LangGraph",
            "combined_insights": "text",
            "summaries": [{"url": "https://a.com", "title": "A", "summary": "x"}],
        })

    assert "# Prose Report" in state["report"]
    assert "structured_report" not in state
