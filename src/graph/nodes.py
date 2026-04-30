"""All LangGraph nodes for the research pipeline."""

import asyncio
import json
import logging
from datetime import datetime, UTC

from src.graph.state import ResearchState
from src.llm.factory import get_llm
from src.observability.context import build_trace_metadata, build_trace_tags
from src.observability.langsmith import start_step_span
from src.tools.search import perform_search
from src.tools.fetcher import fetch_url_content
from src.tools.vector_store import VectorStoreManager
from src.errors import SearchError, FetchError, LLMError

logger = logging.getLogger(__name__)


async def _invoke_llm(
    prompt: str, *, step_name: str, llm, metadata: dict[str, object] | None = None
):
    with start_step_span(
        name=f"{step_name}.llm_invoke",
        run_type="llm",
        node_name=step_name,
        inputs={"prompt": prompt},
        metadata=metadata or {},
        tags=["llm"],
    ):
        return await llm.ainvoke(
            prompt,
            config={
                "tags": build_trace_tags(["llm"]),
                "metadata": build_trace_metadata(metadata or {}),
            },
        )


# ---------------------------------------------------------------------------
# Node 1: Search
# ---------------------------------------------------------------------------


async def search_node(state: ResearchState) -> ResearchState:
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
                results = await asyncio.to_thread(perform_search, query)
            logger.info("[search_node] got %d results", len(results))
            return {**state, "search_results": results, "error": None}
        except SearchError as exc:
            logger.error("[search_node] %s", exc)
            return {**state, "search_results": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Node 2: Retrieve
# ---------------------------------------------------------------------------


async def retrieve_node(state: ResearchState) -> ResearchState:
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
                        text = await fetch_url_content(url)
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


async def summarize_node(state: ResearchState) -> ResearchState:
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
        prepared_sources: list[dict[str, str]] = []
        source_blocks: list[str] = []
        total_chars = 0
        max_total_chars = 50000
        per_source_limit = 10000

        for item in contents:
            text = item.get("raw_text", "").strip()
            if not text:
                continue

            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip()
            if not url:
                continue

            remaining_budget = max_total_chars - total_chars
            if remaining_budget <= 0:
                break

            clipped_text = text[: min(per_source_limit, remaining_budget)]
            if not clipped_text.strip():
                continue

            prepared_sources.append({"url": url, "title": title})
            source_blocks.append(
                f"SOURCE URL: {url}\nSOURCE TITLE: {title}\nCONTENT:\n{clipped_text}"
            )
            total_chars += len(clipped_text)

        if not source_blocks:
            return {**state, "summaries": []}

        prompt = (
            "You are a research assistant. Create high-coverage source summaries relevant "
            f"to the query '{query}'.\n"
            "Return ONLY valid JSON with this exact schema:\n"
            '[{"url":"<source-url>","title":"<source-title>","summary":"<3-5 sentences>"}]\n\n'
            "Rules:\n"
            "- Include one object per source provided.\n"
            "- Preserve each source URL exactly as provided.\n"
            "- Focus on facts and claims relevant to the query.\n"
            "- Do not include markdown fences or extra text.\n\n"
            "Sources:\n\n"
            + "\n\n---\n\n".join(source_blocks)
        )

        try:
            response = await _invoke_llm(
                prompt,
                step_name="summarize",
                llm=llm,
                metadata={"source_count": len(source_blocks), "query": query},
            )
            response_text = (
                str(response.content) if hasattr(response, "content") else str(response)
            ).strip()

            parsed = json.loads(response_text)
            if not isinstance(parsed, list):
                raise ValueError("LLM summarize output must be a JSON list")

            parsed_by_url: dict[str, dict[str, str]] = {}
            for entry in parsed:
                if not isinstance(entry, dict):
                    continue
                url = str(entry.get("url", "")).strip()
                title = str(entry.get("title", "")).strip()
                summary = str(entry.get("summary", "")).strip()
                if url and summary:
                    parsed_by_url[url] = {"url": url, "title": title, "summary": summary}

            summaries: list[dict[str, str]] = []
            for source in prepared_sources:
                url = source["url"]
                fallback_title = source["title"]
                if url in parsed_by_url:
                    row = parsed_by_url[url]
                    if not row.get("title"):
                        row["title"] = fallback_title
                    summaries.append(row)

            if not summaries:
                raise ValueError("LLM summarize output did not include matched source summaries")

            return {**state, "summaries": summaries}
        except Exception as exc:
            raise LLMError(f"Summarization failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Node 4: Combine
# ---------------------------------------------------------------------------


async def combine_node(state: ResearchState) -> ResearchState:
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
            f"(3–6 paragraphs). Do not repeat the same point from multiple sources; instead merge "
            f"and reconcile them.\n\n{summaries_text}\n\n"
            f"Prior context from past internal reports (may be stale):\n{memory_context}"
        )

        llm = get_llm(temperature=0.3)
        try:
            response = await _invoke_llm(
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


async def report_node(state: ResearchState) -> ResearchState:
    """Generate a final structured markdown report.

    Populates ``report`` and ``report_metadata``.
    """
    query = state.get("query", "")
    combined = state.get("combined_insights", "")
    summaries = state.get("summaries", [])
    with start_step_span(
        name="report_node",
        run_type="chain",
        node_name="report",
        inputs={"summary_count": len(summaries)},
    ):
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
            response = await _invoke_llm(
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


async def vector_store_node(state: ResearchState) -> ResearchState:
    """Persist the final report to Pinecone (runs only when enabled).

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

        logger.info("[vector_store_node] saving report to Pinecone")
        manager = VectorStoreManager()
        try:
            with start_step_span(
                name="vector_store_node.save_report",
                run_type="tool",
                node_name="vector_store",
                inputs={"query": query},
                tags=["external", "pinecone"],
            ):
                doc_id = await asyncio.to_thread(
                    manager.save_report,
                    query=query,
                    report=report,
                    metadata=metadata,
                )
            logger.info("[vector_store_node] saved as %s", doc_id)
        except Exception as exc:
            # Non-fatal: log the error but don't abort the pipeline
            logger.warning("[vector_store_node] could not save: %s", exc)

        return state


# ---------------------------------------------------------------------------
# Node 7: Memory Context
# ---------------------------------------------------------------------------


async def memory_context_node(state: ResearchState) -> ResearchState:
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
                tags=["external", "pinecone"],
            ):
                context = await asyncio.wait_for(
                    asyncio.to_thread(vector_store.search_reports, query),
                    timeout=8,
                )
            if context:
                context = "\n\n".join([c["document"] for c in context])[:2000]
            else:
                context = ""

            return {**state, "memory_context": context}
        except asyncio.TimeoutError:
            logger.warning("[memory_context_node] timed out while fetching context; continuing without memory context.")
            return {**state, "memory_context": ""}
        except Exception as exc:
            logger.warning("[memory_context_node] could not generate context: %s", exc)
            return {**state, "memory_context": ""}
