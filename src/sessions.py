"""In-memory session store for multi-turn research conversations."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC


@dataclass
class SessionRun:
    """A single completed research run inside a session."""
    run_id: str
    query: str
    source_urls: list[str] = field(default_factory=list)
    report: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "source_urls": self.source_urls,
            "report": self.report,
            "created_at": self.created_at,
        }


@dataclass
class ConversationTurn:
    """One turn in the session conversation (user question or assistant answer)."""
    role: str            # "user" | "assistant"
    content: str
    run_id: str | None = None
    citations: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "run_id": self.run_id,
            "citations": self.citations,
            "created_at": self.created_at,
        }


@dataclass
class Session:
    """An ongoing research session with runs and conversation history."""
    session_id: str
    runs: list[SessionRun] = field(default_factory=list)
    conversation: list[ConversationTurn] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def latest_run(self) -> SessionRun | None:
        return self.runs[-1] if self.runs else None

    def get_run(self, run_id: str) -> SessionRun | None:
        return next((r for r in self.runs if r.run_id == run_id), None)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "runs": [r.to_dict() for r in self.runs],
            "conversation": [t.to_dict() for t in self.conversation],
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# In-memory store (keyed by session_id)
# ---------------------------------------------------------------------------

_sessions: dict[str, Session] = {}


def create_session() -> Session:
    """Create a new session and register it in the store."""
    session = Session(session_id=str(uuid.uuid4()))
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> Session | None:
    """Return the session for the given ID, or None if not found."""
    return _sessions.get(session_id)


def generate_run_id() -> str:
    return str(uuid.uuid4())
