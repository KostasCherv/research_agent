"""Internal Rag Anything-compatible sidecar service.

This service owns retrieval persistence (index/graph artifacts) and is deployed
as a separate process from the main API.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config import settings


app = FastAPI(
    title="Research Agent RAG Sidecar",
    description="Internal sidecar that manages RAG ingestion/query persistence.",
    version="0.1.0",
)


@dataclass
class SidecarPaths:
    base: Path
    jobs: Path
    resources: Path


def _paths() -> SidecarPaths:
    base = Path(settings.rag_sidecar_persist_directory).expanduser().resolve()
    jobs = base / "jobs"
    resources = base / "resources"
    jobs.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    return SidecarPaths(base=base, jobs=jobs, resources=resources)


def _job_path(job_id: str) -> Path:
    return _paths().jobs / f"{job_id}.json"


def _resource_path(resource_id: str) -> Path:
    return _paths().resources / f"{resource_id}.json"


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


def _extract_text(file_locator: str) -> str:
    path = Path(file_locator)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_locator}")

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except Exception as exc:
            raise RuntimeError("pypdf is required for PDF ingestion") from exc
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    if suffix == ".docx":
        try:
            from docx import Document
        except Exception as exc:
            raise RuntimeError("python-docx is required for DOCX ingestion") from exc
        doc = Document(str(path))
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


def _write_job(job_id: str, payload: dict[str, Any]) -> None:
    _job_path(job_id).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/ingest")
async def ingest(body: IngestRequest):
    _write_job(
        body.job_id,
        {
            "job_id": body.job_id,
            "resource_id": body.resource_id,
            "status": "running",
            "stage": "ingesting",
            "error": None,
        },
    )

    try:
        text = _extract_text(body.file_locator)
        chunks = _chunk_text(text)
        record = {
            "resource_id": body.resource_id,
            "owner_scope": body.owner_scope,
            "workspace_id": body.workspace_id,
            "file_locator": body.file_locator,
            "chunks": chunks,
        }
        _resource_path(body.resource_id).write_text(
            json.dumps(record, ensure_ascii=False),
            encoding="utf-8",
        )
        _write_job(
            body.job_id,
            {
                "job_id": body.job_id,
                "resource_id": body.resource_id,
                "status": "succeeded",
                "stage": "completed",
                "error": None,
            },
        )
        return {
            "job_id": body.job_id,
            "resource_id": body.resource_id,
            "status": "succeeded",
            "chunk_count": len(chunks),
        }
    except Exception as exc:
        _write_job(
            body.job_id,
            {
                "job_id": body.job_id,
                "resource_id": body.resource_id,
                "status": "failed",
                "stage": "failed",
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/ingest/{job_id}")
async def ingest_status(job_id: str):
    payload = _read_json(_job_path(job_id))
    if not payload:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return payload


@app.post("/query")
async def query(body: QueryRequest):
    query_tokens = set(_tokenize(body.query))
    scored: list[tuple[float, dict[str, Any]]] = []

    for resource_id in body.resource_ids:
        resource_payload = _read_json(_resource_path(resource_id))
        if not resource_payload:
            continue
        if resource_payload.get("owner_scope") != body.owner_scope:
            continue
        if resource_payload.get("workspace_id") != body.workspace_id:
            continue

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
                        "resource_id": resource_id,
                        "chunk_id": f"{resource_id}:{idx}",
                        "text": chunk,
                        "source_title": Path(resource_payload.get("file_locator", "")).name,
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
    path = _resource_path(resource_id)
    if path.exists():
        path.unlink()
    return {"resource_id": resource_id, "deleted": True}
