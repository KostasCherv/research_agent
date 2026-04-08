"""All LangGraph nodes for the research pipeline."""

import asyncio
import logging
from datetime import datetime, UTC

from pydantic import ValidationError

from src.graph.state import ResearchState
from src.llm.factory import get_llm
from src.llm.output_parsers import StructuredReportV2
from src.observability.context import build_trace_metadata, build_trace_tags
from src.observability.langsmith import start_step_span
from src.tools.search import perform_search
from src.tools.fetcher import fetch_url_content
from src.tools.vector_store import VectorStoreManager
from src.errors import SearchError, FetchError, LLMError

logger = logging.getLogger(__name__)


def _invoke_llm(prompt: str, *, step_name: str, llm, metadata: dict[str, object] | None = None):
    with start_step_span(
        name=f"{step_name}.llm_invoke",
        run_type="llm",
        node_name=step_name,
        inputs={"prompt": prompt},
        metadata=metadata or {},
        tags=["llm"],
    ):
        return llm.invoke(
            prompt,
            config={
                "tags": build_trace_tags(["llm"]),
                "metadata": build_trace_metadata(metadata or {}),
            },
        )


# ---------------------------------------------------------------------------
# Node 1: Search
# ---------------------------------------------------------------------------


def search_node(state: ResearchState) -> ResearchState:
    """Run a Tavily web search for the user query.

    Populates ``search_results`` or sets ``error`` on failure.
    """
    query = state.get("query", "")
    with start_step_span(
        name="search_node",
        run_type="chain",
        node_name="search",
        inputs={"query": query},
    ):
        logger.info("[search_node] query=%r", query)
        try:
            with start_step_span(
                name="search_node.tavily_search",
                run_type="tool",
                node_name="search",
                inputs={"query": query},
                tags=["external", "tavily"],
            ):
                results = perform_search(query)
            logger.info("[search_node] got %d results", len(results))
            return {**state, "search_results": results, "error": None}
        except SearchError as exc:
            logger.error("[search_node] %s", exc)
            return {**state, "search_results": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Node 2: Retrieve
# ---------------------------------------------------------------------------


def retrieve_node(state: ResearchState) -> ResearchState:
    """Fetch full text for each search-result URL (up to 2 retries each).

    Populates ``retrieved_contents``.
    """
    results = state.get("search_results", [])
    with start_step_span(
        name="retrieve_node",
        run_type="chain",
        node_name="retrieve",
        inputs={"result_count": len(results)},
    ):
        logger.info("[retrieve_node] fetching %d URLs", len(results))

        retrieved: list[dict] = []
        for item in results:
            url = item.get("url", "")
            if not url:
                continue
            for attempt in range(1, 3):
                try:
                    with start_step_span(
                        name="retrieve_node.fetch_url",
                        run_type="tool",
                        node_name="retrieve",
                        inputs={"url": url, "attempt": attempt},
                        tags=["external", "http"],
                    ):
                        text = asyncio.run(fetch_url_content(url))
                    retrieved.append(
                        {"url": url, "title": item.get("title", ""), "raw_text": text}
                    )
                    break
                except FetchError as exc:
                    logger.warning(
                        "[retrieve_node] attempt %d failed for %s: %s", attempt, url, exc
                    )
                    if attempt == 2:
                        # Fall back to the Tavily snippet
                        retrieved.append(
                            {
                                "url": url,
                                "title": item.get("title", ""),
                                "raw_text": item.get("content", ""),
                            }
                        )

        return {**state, "retrieved_contents": retrieved}


# ---------------------------------------------------------------------------
# Node 3: Summarize
# ---------------------------------------------------------------------------


def summarize_node(state: ResearchState) -> ResearchState:
    """Ask the LLM to summarize each retrieved source.

    Populates ``summaries``.
    """
    contents = state.get("retrieved_contents", [])
    query = state.get("query", "")
    with start_step_span(
        name="summarize_node",
        run_type="chain",
        node_name="summarize",
        inputs={"source_count": len(contents)},
    ):
        logger.info("[summarize_node] summarizing %d sources", len(contents))

        llm = get_llm(temperature=0.2)
        summaries: list[dict] = []

        for item in contents:
            text = item.get("raw_text", "")[:6000]
            if not text.strip():
                continue
            prompt = (
                f"You are a research assistant. Summarize the following article in 3–5 sentences, "
                f"focusing on information relevant to the query: '{query}'.\n\n"
                f"Article ({item['url']}):\n{text}"
            )
            try:
                response = _invoke_llm(
                    prompt,
                    step_name="summarize",
                    llm=llm,
                    metadata={"source_url": item["url"]},
                )
                summary_text = (
                    str(response.content) if hasattr(response, "content") else str(response)
                )
                summaries.append(
                    {
                        "url": item["url"],
                        "title": item["title"],
                        "summary": summary_text.strip(),
                    }
                )
            except Exception as exc:
                raise LLMError(f"Summarization failed for {item['url']}: {exc}") from exc

        return {**state, "summaries": summaries}


# ---------------------------------------------------------------------------
# Node 4: Combine
# ---------------------------------------------------------------------------


def combine_node(state: ResearchState) -> ResearchState:
    """Merge all per-source summaries into a single coherent synthesis.

    Populates ``combined_insights``.
    """
    summaries = state.get("summaries", [])
    query = state.get("query", "")
    with start_step_span(
        name="combine_node",
        run_type="chain",
        node_name="combine",
        inputs={"summary_count": len(summaries)},
    ):
        logger.info("[combine_node] combining %d summaries", len(summaries))

        summaries_text = "\n\n".join(
            f"Source: {s['title']} ({s['url']})\n{s['summary']}" for s in summaries
        )
        memory_context = state.get("memory_context", "")
        prompt = (
            f"You are a research analyst. Given the following source summaries for the query "
            f"'{query}', write a comprehensive and well-structured synthesis of the key insights "
            f"(3–6 paragraphs). Identify the most important discrete claims found across sources, "
            f"noting where sources agree or disagree. Do not repeat the same point from multiple "
            f"sources; instead merge and reconcile them. For each key claim, indicate which source "
            f"URLs support it.\n\n{summaries_text}\n\n"
            f"Prior context from past internal reports (may be stale):\n{memory_context}"
        )

        llm = get_llm(temperature=0.3)
        try:
            response = _invoke_llm(
                prompt,
                step_name="combine",
                llm=llm,
                metadata={"summary_count": len(summaries)},
            )
            combined = (
                str(response.content) if hasattr(response, "content") else str(response)
            )
            return {**state, "combined_insights": combined.strip()}
        except Exception as exc:
            raise LLMError(f"Combine step failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Node 5: Report
# ---------------------------------------------------------------------------


def report_node(state: ResearchState) -> ResearchState:
    """Generate a final report.

    When ``enable_structured_report_v2`` is True, produces a claim-centric
    ``StructuredReportV2`` and renders it to markdown.  Falls back to the
    original prose report on parse failures, setting ``error`` only when
    both attempts fail.

    Populates ``report``, ``report_metadata``, and (v2) ``structured_report``,
    ``claims``, ``source_assessments``.
    """
    from src.config import settings

    query = state.get("query", "")
    combined = state.get("combined_insights", "")
    summaries = state.get("summaries", [])

    with start_step_span(
        name="report_node",
        run_type="chain",
        node_name="report",
        inputs={"summary_count": len(summaries), "structured_v2": settings.enable_structured_report_v2},
    ):
        logger.info("[report_node] generating report (v2=%s)", settings.enable_structured_report_v2)

        metadata = {
            "title": query,
            "sources": [s.get("url", "") for s in summaries],
            "generated_at": datetime.now(UTC).isoformat(),
        }

        if settings.enable_structured_report_v2:
            return _report_node_v2(state, query, combined, summaries, metadata)

        return _report_node_v1(state, query, combined, summaries, metadata)


def _build_structured_prompt(query: str, combined: str, summaries: list[dict]) -> str:
    """Build the prompt for structured v2 report generation."""
    sources_block = "\n".join(
        f"- {s.get('title', 'Untitled')} ({s.get('url', '')})" for s in summaries if s.get("url")
    )
    return (
        f"You are a professional research analyst. Based on the synthesis below, produce a "
        f"structured research report for the query: '{query}'.\n\n"
        f"Requirements:\n"
        f"- Extract 3–8 discrete, verifiable CLAIMS from the research.\n"
        f"- For each claim assign a confidence score (0.0–1.0) based on source agreement and evidence quality.\n"
        f"- Link each claim to the source URLs that support it.\n"
        f"- Assess each source for reliability (0.0–1.0) and note any bias or quality concerns.\n"
        f"- Write a concise executive summary and conclusion.\n\n"
        f"Available sources:\n{sources_block}\n\n"
        f"Synthesis:\n{combined}"
    )


def _report_node_v2(
    state: ResearchState,
    query: str,
    combined: str,
    summaries: list[dict],
    metadata: dict,
) -> ResearchState:
    """Structured output report with retry on parse failure."""
    llm = get_llm(temperature=0.1)
    structured_llm = llm.with_structured_output(StructuredReportV2)
    prompt = _build_structured_prompt(query, combined, summaries)

    structured: StructuredReportV2 | None = None
    for attempt in range(1, 3):
        try:
            with start_step_span(
                name=f"report_node.structured_invoke.attempt_{attempt}",
                run_type="llm",
                node_name="report",
                inputs={"attempt": attempt},
                tags=["llm", "structured"],
            ):
                structured = structured_llm.invoke(prompt)
            break
        except (ValidationError, Exception) as exc:
            logger.warning("[report_node] structured attempt %d failed: %s", attempt, exc)
            if attempt == 2:
                # Deterministic user-visible error — both attempts exhausted
                error_msg = (
                    "Report generation failed: could not produce a valid structured report "
                    "after 2 attempts. Please try again or disable structured output."
                )
                return {**state, "error": error_msg, "report": "", "report_metadata": metadata}

    assert structured is not None  # guarded by loop above
    report_text = structured.to_markdown()
    return {
        **state,
        "report": report_text,
        "report_metadata": metadata,
        "structured_report": structured.model_dump(),
        "claims": [c.model_dump() for c in structured.claims],
        "source_assessments": [sa.model_dump() for sa in structured.source_assessments],
    }


def _report_node_v1(
    state: ResearchState,
    query: str,
    combined: str,
    summaries: list[dict],
    metadata: dict,
) -> ResearchState:
    """Original prose-based report generation (backward-compatible)."""
    sources_md = "\n".join(
        f"- [{s['title']}]({s['url']})" for s in summaries if s.get("url")
    )
    prompt = (
        f"You are a professional research report writer. Based on the synthesis below, "
        f"produce a polished markdown report with:\n"
        f"1. A clear title (H1)\n"
        f"2. An executive summary section\n"
        f"3. Key findings as bullet points\n"
        f"4. A conclusion\n\n"
        f"Query: {query}\n\nSynthesis:\n{combined}"
    )

    llm = get_llm(temperature=0.2)
    try:
        response = _invoke_llm(
            prompt,
            step_name="report",
            llm=llm,
            metadata={"summary_count": len(summaries)},
        )
        report_text = (
            str(response.content) if hasattr(response, "content") else str(response)
        )
        report_text = report_text.strip()
    except Exception as exc:
        raise LLMError(f"Report generation failed: {exc}") from exc

    if sources_md:
        report_text += f"\n\n## References\n\n{sources_md}"

    return {**state, "report": report_text, "report_metadata": metadata}


# ---------------------------------------------------------------------------
# Node 6: Vector Store
# ---------------------------------------------------------------------------


def vector_store_node(state: ResearchState) -> ResearchState:
    """Persist the final report to ChromaDB (runs only when enabled).

    This node is a no-op if ``use_vector_store`` is False.
    """
    with start_step_span(
        name="vector_store_node",
        run_type="chain",
        node_name="vector_store",
        inputs={"enabled": bool(state.get("use_vector_store", False))},
    ):
        if not state.get("use_vector_store", False):
            logger.info("[vector_store_node] skipping (use_vector_store=False)")
            return state

        report = state.get("report", "")
        query = state.get("query", "")
        metadata = state.get("report_metadata", {})

        logger.info("[vector_store_node] saving report to Chroma")
        manager = VectorStoreManager()
        try:
            with start_step_span(
                name="vector_store_node.save_report",
                run_type="tool",
                node_name="vector_store",
                inputs={"query": query},
                tags=["external", "chroma"],
            ):
                doc_id = manager.save_report(query=query, report=report, metadata=metadata)
            logger.info("[vector_store_node] saved as %s", doc_id)
        except Exception as exc:
            # Non-fatal: log the error but don't abort the pipeline
            logger.warning("[vector_store_node] could not save: %s", exc)

        return state


# ---------------------------------------------------------------------------
# Node 7: Memory Context
# ---------------------------------------------------------------------------


def memory_context_node(state: ResearchState) -> ResearchState:
    """Generate a memory context for the LLM using the vector store.

    Populates ``memory_context`` with the most relevant reports from the vector store.
    """
    with start_step_span(
        name="memory_context_node",
        run_type="chain",
        node_name="memory_context",
        inputs={},
    ):
        try:
            vector_store = VectorStoreManager()
            query = state.get("query", "")
            with start_step_span(
                name="memory_context_node.search_reports",
                run_type="retriever",
                node_name="memory_context",
                inputs={"query": query, "n_results": 3},
                tags=["external", "chroma"],
            ):
                context = vector_store.search_reports(query)
            if context:
                context = "\n\n".join([c["document"] for c in context])[:2000]
            else:
                context = ""

            return {**state, "memory_context": context}
        except Exception as exc:
            logger.warning("[memory_context_node] could not generate context: %s", exc)
            return {**state, "memory_context": ""}