"""Internal Rag Anything-compatible sidecar service.

This service owns retrieval persistence (index/graph artifacts) and is deployed
as a separate process from the main API.
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.db.supabase_store import SupabaseSessionStore


app = FastAPI(
    title="Research Agent RAG Sidecar",
    description="Internal sidecar that manages RAG ingestion/query persistence.",
    version="0.1.0",
)

_store: SupabaseSessionStore | None = None


def _get_store() -> SupabaseSessionStore:
    global _store
    if _store is None:
        _store = SupabaseSessionStore()
    return _store


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower()) if t]


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


async def _read_locator_bytes(file_locator: str) -> tuple[bytes, str]:
    parsed = urlparse(file_locator)
    if parsed.scheme in {"http", "https"}:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(file_locator)
        response.raise_for_status()
        return response.content, Path(parsed.path).suffix.lower()

    path = Path(file_locator)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_locator}")
    return path.read_bytes(), path.suffix.lower()


def _extract_text_from_bytes(content: bytes, suffix: str) -> str:
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except Exception as exc:
            raise RuntimeError("pypdf is required for PDF ingestion") from exc
        reader = PdfReader(BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    if suffix == ".docx":
        try:
            from docx import Document
        except Exception as exc:
            raise RuntimeError("python-docx is required for DOCX ingestion") from exc
        doc = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)

    raise RuntimeError(f"Unsupported file type in sidecar: {suffix}")


class IngestRequest(BaseModel):
    resource_id: str
    file_locator: str
    owner_scope: str
    workspace_id: str
    job_id: str


class QueryRequest(BaseModel):
    agent_id: str
    resource_ids: list[str]
    query: str
    owner_scope: str
    workspace_id: str

@app.post("/ingest")
async def ingest(body: IngestRequest):
    try:
        content, suffix = await _read_locator_bytes(body.file_locator)
        text = _extract_text_from_bytes(content, suffix)
        chunks = _chunk_text(text)
        await _get_store().upsert_rag_sidecar_artifact(
            resource_id=body.resource_id,
            owner_id=body.owner_scope,
            workspace_id=body.workspace_id,
            source_locator=body.file_locator,
            chunks=chunks,
        )
        return {
            "job_id": body.job_id,
            "resource_id": body.resource_id,
            "status": "succeeded",
            "chunk_count": len(chunks),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/ingest/{job_id}")
async def ingest_status(job_id: str):
    payload = await _get_store().get_rag_ingestion_job(job_id)
    if not payload:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return payload


@app.post("/query")
async def query(body: QueryRequest):
    query_tokens = set(_tokenize(body.query))
    scored: list[tuple[float, dict[str, Any]]] = []

    payloads = await _get_store().list_rag_sidecar_artifacts(
        resource_ids=body.resource_ids,
        owner_id=body.owner_scope,
        workspace_id=body.workspace_id,
    )

    for resource_payload in payloads:
        for idx, chunk in enumerate(resource_payload.get("chunks") or []):
            if not isinstance(chunk, str):
                continue
            tokens = set(_tokenize(chunk))
            score = float(len(query_tokens & tokens))
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "resource_id": resource_payload["resource_id"],
                        "chunk_id": f"{resource_payload['resource_id']}:{idx}",
                        "text": chunk,
                        "source_title": Path(resource_payload.get("source_locator", "")).name,
                        "source_url": "",
                    },
                )
            )

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = [item for _, item in scored[:8]]
    context = "\n\n".join(
        f"[resource:{chunk['resource_id']} chunk:{chunk['chunk_id']}]\n{chunk['text']}"
        for chunk in top
    )
    return {"context": context, "chunks": top}


@app.delete("/resource/{resource_id}")
async def delete_resource(resource_id: str):
    await _get_store().delete_rag_sidecar_artifact(resource_id=resource_id)
    return {"resource_id": resource_id, "deleted": True}
