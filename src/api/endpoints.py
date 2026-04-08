"""FastAPI application — /health, /research (SSE), and session endpoints."""

import json
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.graph.graph import build_graph
from src.errors import ResearchAgentError
from src.observability import end_workflow_run, start_workflow_run
from src.sessions import (
    Session,
    ConversationTurn,
    create_session,
    generate_run_id,
    get_session,
)
from src.tools.vector_store import VectorStoreManager
from src.llm.factory import get_llm

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Research Agent API",
    description="Multi-step LangGraph research orchestration with SSE streaming.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    query: str
    use_vector_store: bool = False


class FollowupRequest(BaseModel):
    question: str
    run_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(ResearchAgentError)
async def research_agent_error_handler(request: Request, exc: ResearchAgentError):
    raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Shared streaming logic
# ---------------------------------------------------------------------------

async def _stream_research(
    query: str,
    use_vector_store: bool,
    session: Session | None = None,
    run_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Run the research graph and stream node events as SSE.

    When ``session`` and ``run_id`` are provided the final state is recorded
    on the session and source chunks are persisted for follow-up retrieval.
    """
    graph = build_graph()
    initial_state: dict = {
        "query": query,
        "use_vector_store": use_vector_store,
        "error": None,
        "session_id": session.session_id if session else None,
        "run_id": run_id,
        "conversation_history": (
            [t.to_dict() for t in session.conversation] if session else []
        ),
    }

    with start_workflow_run(
        entrypoint="api",
        query=query,
        use_vector_store=use_vector_store,
    ) as trace_ctx:
        final_node_state: dict | None = None
        try:
            async for event in graph.astream(initial_state):
                for node_name, node_state in event.items():
                    final_node_state = node_state
                    payload = {
                        "workflow_id": trace_ctx.workflow_id,
                        "node": node_name,
                        "data": {
                            k: v
                            for k, v in node_state.items()
                            if k in {"error", "report", "combined_insights"}
                        },
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            # Persist session state after a successful run
            if session is not None and run_id is not None and final_node_state:
                _record_session_run(session, run_id, query, final_node_state)

            end_workflow_run(
                trace_ctx,
                status="success",
                outputs={
                    "node": "__end__",
                    "has_report": bool(final_node_state and final_node_state.get("report")),
                    "has_error": bool(final_node_state and final_node_state.get("error")),
                },
            )
            yield (
                f"data: {json.dumps({'workflow_id': trace_ctx.workflow_id, 'node': '__end__', 'data': {}})}\n\n"
            )
        except Exception as exc:
            end_workflow_run(trace_ctx, status="error", error=str(exc))
            error_payload = {
                "workflow_id": trace_ctx.workflow_id,
                "node": "__error__",
                "data": {"error": str(exc)},
            }
            yield f"data: {json.dumps(error_payload)}\n\n"


def _record_session_run(
    session: Session,
    run_id: str,
    query: str,
    final_state: dict,
) -> None:
    """Persist run metadata and source chunks to the session store."""
    from src.sessions import SessionRun

    retrieved = final_state.get("retrieved_contents") or []
    summaries = final_state.get("summaries") or []
    source_urls = [s.get("url", "") for s in retrieved if s.get("url")]

    run = SessionRun(
        run_id=run_id,
        query=query,
        source_urls=source_urls,
        report=final_state.get("report", ""),
    )
    session.runs.append(run)

    # Persist source chunks for follow-up retrieval
    sources_to_chunk = retrieved if retrieved else summaries
    if sources_to_chunk:
        try:
            manager = VectorStoreManager()
            manager.save_source_chunks(
                run_id=run_id,
                session_id=session.session_id,
                sources=sources_to_chunk,
            )
        except Exception as exc:
            logger.warning("[session] could not save source chunks: %s", exc)


async def _stream_followup(
    session: Session,
    question: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """Retrieve run-scoped sources and stream a cited answer."""
    # Retrieve relevant source chunks
    try:
        manager = VectorStoreManager()
        chunks = manager.search_run_sources(question, run_id=run_id, n_results=5)
    except Exception as exc:
        logger.warning("[followup] source retrieval failed: %s", exc)
        chunks = []

    context_block = "\n\n".join(
        f"[Source: {c['source_title']} ({c['source_url']})]\n{c['text']}"
        for c in chunks
    )

    history_block = "\n".join(
        f"{t.role.upper()}: {t.content}" for t in session.conversation[-6:]
    )

    prompt = (
        f"You are a research assistant answering a follow-up question.\n\n"
        f"Conversation so far:\n{history_block}\n\n"
        f"Retrieved source passages:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        f"Answer concisely and cite the source URLs inline using [Source N] notation. "
        f"At the end, list the citations."
    )

    llm = get_llm(temperature=0.2)
    full_answer = ""

    try:
        async for chunk in llm.astream(prompt):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_answer += token
            yield f"data: {json.dumps({'type': 'chunk', 'text': token})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
        return

    # Build citations from retrieved chunks (deduplicate by URL)
    seen: set[str] = set()
    citations: list[dict] = []
    for c in chunks:
        url = c["source_url"]
        if url and url not in seen:
            seen.add(url)
            citations.append({"source_url": url, "source_title": c["source_title"]})

    # Record turns in conversation history
    session.conversation.append(
        ConversationTurn(role="user", content=question, run_id=run_id)
    )
    session.conversation.append(
        ConversationTurn(
            role="assistant",
            content=full_answer,
            run_id=run_id,
            citations=citations,
        )
    )

    yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health():
    """Simple liveness probe."""
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/research", tags=["Research"])
async def research(body: ResearchRequest):
    """Run the research pipeline and stream progress via Server-Sent Events."""
    return StreamingResponse(
        _stream_research(body.query, body.use_vector_store),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

@app.post("/sessions", tags=["Sessions"])
async def create_session_endpoint():
    """Create a new research session."""
    session = create_session()
    return {"session_id": session.session_id, "created_at": session.created_at}


@app.get("/sessions/{session_id}", tags=["Sessions"])
async def get_session_endpoint(session_id: str):
    """Return session state including runs and conversation history."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session.to_dict()


@app.post("/sessions/{session_id}/research", tags=["Sessions"])
async def session_research(session_id: str, body: ResearchRequest):
    """Run research within a session and persist the run for follow-up."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    run_id = generate_run_id()
    return StreamingResponse(
        _stream_research(body.query, body.use_vector_store, session=session, run_id=run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Run-Id": run_id,
        },
    )


@app.post("/sessions/{session_id}/followup", tags=["Sessions"])
async def session_followup(session_id: str, body: FollowupRequest):
    """Ask a follow-up question grounded to a session's source material."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    # Resolve which run to ground the follow-up against
    if body.run_id:
        run = session.get_run(body.run_id)
        if run is None:
            raise HTTPException(
                status_code=404,
                detail=f"Run '{body.run_id}' not found in session '{session_id}'.",
            )
        run_id = body.run_id
    else:
        latest = session.latest_run()
        if latest is None:
            raise HTTPException(
                status_code=400,
                detail="No research runs found in this session. Run /research first.",
            )
        run_id = latest.run_id

    return StreamingResponse(
        _stream_followup(session, body.question, run_id=run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
