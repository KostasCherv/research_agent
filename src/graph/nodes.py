"""All LangGraph nodes for the research pipeline."""

import asyncio
import logging
from datetime import datetime, UTC

from src.graph.state import ResearchState
from src.llm.factory import get_llm
from src.tools.search import perform_search
from src.tools.fetcher import fetch_url_content
from src.tools.vector_store import VectorStoreManager
from src.errors import SearchError, FetchError, LLMError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node 1: Search
# ---------------------------------------------------------------------------

def search_node(state: ResearchState) -> ResearchState:
    """Run a Tavily web search for the user query.

    Populates ``search_results`` or sets ``error`` on failure.
    """
    query = state.get("query", "")
    logger.info("[search_node] query=%r", query)
    try:
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
    logger.info("[retrieve_node] fetching %d URLs", len(results))

    retrieved: list[dict] = []
    for item in results:
        url = item.get("url", "")
        if not url:
            continue
        for attempt in range(1, 3):
            try:
                text = asyncio.run(fetch_url_content(url))
                retrieved.append({"url": url, "title": item.get("title", ""), "raw_text": text})
                break
            except FetchError as exc:
                logger.warning("[retrieve_node] attempt %d failed for %s: %s", attempt, url, exc)
                if attempt == 2:
                    # Fall back to the Tavily snippet
                    retrieved.append({
                        "url": url,
                        "title": item.get("title", ""),
                        "raw_text": item.get("content", ""),
                    })

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
            response = llm.invoke(prompt)
            summary_text = str(response.content) if hasattr(response, "content") else str(response)
            summaries.append({
                "url": item["url"],
                "title": item["title"],
                "summary": summary_text.strip(),
            })
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
    logger.info("[combine_node] combining %d summaries", len(summaries))

    summaries_text = "\n\n".join(
        f"Source: {s['title']} ({s['url']})\n{s['summary']}" for s in summaries
    )
    prompt = (
        f"You are a research analyst. Given the following source summaries for the query "
        f"'{query}', write a comprehensive and well-structured synthesis of the key insights "
        f"(3–6 paragraphs). Do not repeat the same point from multiple sources; instead merge "
        f"and reconcile them.\n\n{summaries_text}"
    )

    llm = get_llm(temperature=0.3)
    try:
        response = llm.invoke(prompt)
        combined = str(response.content) if hasattr(response, "content") else str(response)
        return {**state, "combined_insights": combined.strip()}
    except Exception as exc:
        raise LLMError(f"Combine step failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Node 5: Report
# ---------------------------------------------------------------------------

def report_node(state: ResearchState) -> ResearchState:
    """Generate a final structured markdown report.

    Populates ``report`` and ``report_metadata``.
    """
    query = state.get("query", "")
    combined = state.get("combined_insights", "")
    summaries = state.get("summaries", [])
    logger.info("[report_node] generating report")

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
        response = llm.invoke(prompt)
        report_text = str(response.content) if hasattr(response, "content") else str(response)
        report_text = report_text.strip()
    except Exception as exc:
        raise LLMError(f"Report generation failed: {exc}") from exc

    metadata = {
        "title": query,
        "sources": [s.get("url", "") for s in summaries],
        "generated_at": datetime.now(UTC).isoformat(),
    }

    # Append references section
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
    if not state.get("use_vector_store", False):
        logger.info("[vector_store_node] skipping (use_vector_store=False)")
        return state

    report = state.get("report", "")
    query = state.get("query", "")
    metadata = state.get("report_metadata", {})

    logger.info("[vector_store_node] saving report to Chroma")
    manager = VectorStoreManager()
    try:
        doc_id = manager.save_report(query=query, report=report, metadata=metadata)
        logger.info("[vector_store_node] saved as %s", doc_id)
    except Exception as exc:
        # Non-fatal: log the error but don't abort the pipeline
        logger.warning("[vector_store_node] could not save: %s", exc)

    return state
