"""FastAPI application with /health and /research (SSE streaming) endpoints."""

import json
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.graph.graph import build_graph
from src.errors import ResearchAgentError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Research Agent API",
    description="Multi-step LangGraph research orchestration with SSE streaming.",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    query: str
    use_vector_store: bool = False


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
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health():
    """Simple liveness probe."""
    return HealthResponse(status="ok", version="0.1.0")


async def _stream_research(query: str, use_vector_store: bool) -> AsyncGenerator[str, None]:
    """Async generator that runs the graph and streams node events as SSE."""
    graph = build_graph()
    initial_state = {
        "query": query,
        "use_vector_store": use_vector_store,
        "error": None,
    }

    try:
        async for event in graph.astream(initial_state):
            for node_name, node_state in event.items():
                payload = {
                    "node": node_name,
                    "data": {
                        k: v
                        for k, v in node_state.items()
                        if k in {"error", "report", "combined_insights"}
                    },
                }
                yield f"data: {json.dumps(payload)}\n\n"

        yield "data: {\"node\": \"__end__\", \"data\": {}}\n\n"
    except Exception as exc:
        error_payload = {"node": "__error__", "data": {"error": str(exc)}}
        yield f"data: {json.dumps(error_payload)}\n\n"


@app.post("/research", tags=["Research"])
async def research(body: ResearchRequest):
    """Run the research pipeline and stream progress via Server-Sent Events.

    Connect with ``Accept: text/event-stream`` to receive live node updates.
    Each SSE event contains JSON with ``node`` and ``data`` fields.
    """
    return StreamingResponse(
        _stream_research(body.query, body.use_vector_store),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
