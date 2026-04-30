"""Compile the LangGraph state machine."""

import logging

from langgraph.graph import StateGraph, END

from src.graph.state import ResearchState
from src.graph.nodes import (
    memory_context_node,
    search_node,
    retrieve_node,
    summarize_node,
    report_node,
    vector_store_node,
)
from src.graph.edges import should_abort, has_results
from src.observability.langsmith import start_step_span

logger = logging.getLogger(__name__)


def _abort_node(state: ResearchState) -> ResearchState:
    """Terminal node reached on pipeline abort."""
    with start_step_span(
        name="abort_node",
        run_type="tool",
        node_name="abort",
        inputs={"has_error": bool(state.get("error"))},
        tags=["terminal"],
    ):
        logger.error("Research pipeline aborted. Error: %s", state.get("error"))
        return state


def _empty_node(state: ResearchState) -> ResearchState:
    """Terminal node reached when search returned no results."""
    with start_step_span(
        name="empty_node",
        run_type="tool",
        node_name="empty",
        inputs={"query": state.get("query", "")},
        tags=["terminal"],
    ):
        logger.warning("Search returned no results for query: %s", state.get("query"))
        return {**state, "report": "No results found for the given query.", "report_metadata": {}}


def build_graph():
    """Build and compile the research agent graph.

    Returns:
        A compiled LangGraph ``CompiledGraph`` ready to invoke.
    """
    builder = StateGraph(ResearchState)

    # Register all nodes
    builder.add_node("search",       search_node)
    builder.add_node("retrieve",     retrieve_node)
    builder.add_node("memory_context", memory_context_node)
    builder.add_node("summarize",    summarize_node)
    builder.add_node("report",       report_node)
    builder.add_node("vector_store", vector_store_node)
    builder.add_node("abort",        _abort_node)
    builder.add_node("empty",        _empty_node)

    # Entry point
    builder.set_entry_point("search")

    # After search: check for hard errors
    builder.add_conditional_edges(
        "search",
        should_abort,
        {"continue": "retrieve", "abort": "abort"},
    )

    # After retrieve: check we actually got results
    builder.add_conditional_edges(
        "retrieve",
        has_results,
        {"ok": "memory_context", "empty": "empty"},
    )

    # Linear tail of the pipeline
    builder.add_edge("memory_context", "summarize")
    builder.add_edge("summarize",    "report")
    builder.add_edge("report",       "vector_store")

    # Terminal edges
    builder.add_edge("vector_store", END)
    builder.add_edge("abort",        END)
    builder.add_edge("empty",        END)

    return builder.compile()
