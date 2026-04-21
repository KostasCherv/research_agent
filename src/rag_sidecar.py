"""HTTP client for the Rag Anything sidecar adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.config import settings


@dataclass
class RagQueryResult:
    """Normalized sidecar query response."""

    context: str
    chunks: list[dict[str, Any]]


class RagSidecarClient:
    """Small adapter around internal sidecar endpoints."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.rag_sidecar_base_url).rstrip("/")

    async def ingest(
        self,
        *,
        resource_id: str,
        file_locator: str,
        owner_scope: str,
        workspace_id: str,
        job_id: str,
    ) -> dict[str, Any]:
        payload = {
            "resource_id": resource_id,
            "file_locator": file_locator,
            "owner_scope": owner_scope,
            "workspace_id": workspace_id,
            "job_id": job_id,
        }
        return await self._request_json("POST", "/ingest", json_body=payload)

    async def ingest_status(self, job_id: str) -> dict[str, Any]:
        return await self._request_json("GET", f"/ingest/{job_id}")

    async def query(
        self,
        *,
        agent_id: str,
        resource_ids: list[str],
        query: str,
        owner_scope: str,
        workspace_id: str,
    ) -> RagQueryResult:
        payload = {
            "agent_id": agent_id,
            "resource_ids": resource_ids,
            "query": query,
            "owner_scope": owner_scope,
            "workspace_id": workspace_id,
        }
        response = await self._request_json("POST", "/query", json_body=payload)
        context = str(response.get("context") or "")
        chunks = response.get("chunks") or []
        if not isinstance(chunks, list):
            chunks = []
        return RagQueryResult(context=context, chunks=chunks)

    async def delete_resource(self, resource_id: str) -> None:
        await self._request_json("DELETE", f"/resource/{resource_id}")

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                json=json_body,
            )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"data": data}
