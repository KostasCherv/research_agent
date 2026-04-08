"""Supabase-backed persistence for user sessions and runs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from src.config import settings

if TYPE_CHECKING:
    from src.sessions import ConversationTurn, Session, SessionRun


class SupabaseSessionStore:
    """Persist sessions in Supabase PostgREST with strict user scoping."""

    def __init__(self) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError(
                "Supabase persistence is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        self._base_url = f"{settings.supabase_url.rstrip('/')}/rest/v1"
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        headers = dict(self._headers)
        if extra_headers:
            headers.update(extra_headers)
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(
                method,
                f"{self._base_url}/{path}",
                params=params,
                json=json_body,
                headers=headers,
            )
        response.raise_for_status()
        return response

    async def create_session(self, user_id: str, title: str) -> Session:
        from src.sessions import Session

        session_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        payload = {
            "id": session_id,
            "user_id": user_id,
            "title": title,
            "created_at": created_at,
        }
        await self._request("POST", "research_sessions", json_body=payload)
        return Session(
            session_id=session_id,
            title=title,
            runs=[],
            conversation=[],
            created_at=created_at,
        )

    async def list_sessions(self, user_id: str) -> list[dict[str, str]]:
        """List lightweight session summaries for a user."""
        response = await self._request(
            "GET",
            "research_sessions",
            params={
                "select": "id,title,created_at",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
            },
        )
        rows = response.json()
        return [
            {
                "session_id": row["id"],
                "title": row.get("title") or "New session",
                "created_at": row.get("created_at", ""),
            }
            for row in rows
        ]

    async def get_session(self, session_id: str, user_id: str) -> Session | None:
        from src.sessions import ConversationTurn, Session, SessionRun

        session_resp = await self._request(
            "GET",
            "research_sessions",
            params={
                "select": "id,title,created_at",
                "id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        session_rows = session_resp.json()
        if not session_rows:
            return None

        runs_resp = await self._request(
            "GET",
            "session_runs",
            params={
                "select": "id,query,source_urls,report,created_at",
                "session_id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "order": "created_at.asc",
            },
        )
        run_rows = runs_resp.json()
        runs = [
            SessionRun(
                run_id=row["id"],
                query=row.get("query", ""),
                source_urls=row.get("source_urls") or [],
                report=row.get("report", ""),
                created_at=row.get("created_at", ""),
            )
            for row in run_rows
        ]

        turns_resp = await self._request(
            "GET",
            "conversation_turns",
            params={
                "select": "role,content,run_id,citations,created_at",
                "session_id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "order": "created_at.asc",
            },
        )
        turn_rows = turns_resp.json()
        conversation = [
            ConversationTurn(
                role=row.get("role", "user"),
                content=row.get("content", ""),
                run_id=row.get("run_id"),
                citations=row.get("citations") or [],
                created_at=row.get("created_at", ""),
            )
            for row in turn_rows
        ]

        session_row = session_rows[0]
        return Session(
            session_id=session_row["id"],
            title=session_row.get("title") or "New session",
            runs=runs,
            conversation=conversation,
            created_at=session_row.get("created_at", ""),
        )

    async def append_run(
        self,
        *,
        user_id: str,
        session_id: str,
        run: SessionRun,
    ) -> None:
        payload = {
            "id": run.run_id,
            "session_id": session_id,
            "user_id": user_id,
            "query": run.query,
            "source_urls": run.source_urls,
            "report": run.report,
            "created_at": run.created_at,
        }
        await self._request("POST", "session_runs", json_body=payload)

    async def append_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        turn: ConversationTurn,
    ) -> None:
        payload = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "run_id": turn.run_id,
            "user_id": user_id,
            "role": turn.role,
            "content": turn.content,
            "citations": turn.citations,
            "created_at": turn.created_at,
        }
        await self._request("POST", "conversation_turns", json_body=payload)
