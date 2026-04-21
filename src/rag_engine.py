"""Shared RAG indexing/query logic used by API, sidecar, and background jobs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx

from src.db.supabase_store import SupabaseSessionStore


@dataclass
class RagQueryResult:
    context: str
    chunks: list[dict]


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


async def read_locator_bytes(file_locator: str) -> tuple[bytes, str]:
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


def extract_text_from_bytes(content: bytes, suffix: str) -> str:
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

    raise RuntimeError(f"Unsupported file type for ingestion: {suffix}")


async def ingest_resource_from_locator(
    *,
    store: SupabaseSessionStore,
    resource_id: str,
    file_locator: str,
    owner_id: str,
    workspace_id: str,
) -> int:
    content, suffix = await read_locator_bytes(file_locator)
    text = extract_text_from_bytes(content, suffix)
    chunks = _chunk_text(text)
    await store.upsert_rag_sidecar_artifact(
        resource_id=resource_id,
        owner_id=owner_id,
        workspace_id=workspace_id,
        source_locator=file_locator,
        chunks=chunks,
    )
    return len(chunks)


async def query_resource_context(
    *,
    store: SupabaseSessionStore,
    resource_ids: list[str],
    owner_id: str,
    workspace_id: str,
    query: str,
) -> RagQueryResult:
    query_tokens = set(_tokenize(query))
    scored: list[tuple[float, dict]] = []

    payloads = await store.list_rag_sidecar_artifacts(
        resource_ids=resource_ids,
        owner_id=owner_id,
        workspace_id=workspace_id,
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
    return RagQueryResult(context=context, chunks=top)


async def delete_resource_artifacts(*, store: SupabaseSessionStore, resource_id: str) -> bool:
    return await store.delete_rag_sidecar_artifact(resource_id=resource_id)
