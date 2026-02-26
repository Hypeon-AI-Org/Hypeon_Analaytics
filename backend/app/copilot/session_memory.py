"""
Copilot session memory store: in-memory store for multi-turn context per session.
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

MAX_MESSAGES_PER_SESSION = 20
MAX_SESSIONS = 100
MAX_SESSIONS_LIST = 50
SESSION_TITLE_MAX_LEN = 50


@dataclass
class SessionMessage:
    role: str
    content: str
    meta: Optional[dict] = None


@dataclass
class SessionState:
    session_id: str
    organization_id: str
    messages: deque = field(default_factory=lambda: deque(maxlen=MAX_MESSAGES_PER_SESSION))
    context_summary: Optional[dict] = None
    title: Optional[str] = None
    updated_at: Optional[float] = None

    def append(self, role: str, content: str, meta: Optional[dict] = None) -> None:
        now = time.time()
        self.updated_at = now
        if role == "user" and (not self.title or not self.title.strip()):
            self.title = (content or "").strip()[:SESSION_TITLE_MAX_LEN] or "New chat"
        self.messages.append(SessionMessage(role=role, content=content, meta=meta))

    def get_messages(self) -> list[dict]:
        return [{"role": m.role, "content": m.content, **(m.meta or {})} for m in self.messages]


class SessionMemoryStore:
    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self._store: dict[tuple[str, str], SessionState] = {}
        self._order: deque = deque(maxlen=max_sessions)

    def _key(self, organization_id: str, session_id: str) -> tuple[str, str]:
        return (organization_id or "default", session_id or "")

    def get_or_create_session(self, organization_id: str, session_id: Optional[str] = None) -> SessionState:
        sid = session_id or str(uuid.uuid4())
        key = self._key(organization_id, sid)
        if key not in self._store:
            if len(self._store) >= self._order.maxlen:
                old = self._order.popleft()
                self._store.pop(old, None)
            self._store[key] = SessionState(session_id=sid, organization_id=organization_id or "default")
            self._order.append(key)
        return self._store[key]

    def append(self, organization_id: str, session_id: str, role: str, content: str, meta: Optional[dict] = None) -> None:
        self.get_or_create_session(organization_id, session_id).append(role, content, meta)

    def get_messages(self, organization_id: str, session_id: str) -> list[dict]:
        state = self._store.get(self._key(organization_id, session_id))
        return state.get_messages() if state else []

    def get_sessions(self, organization_id: str) -> list[dict]:
        """Return sessions for the org as [{ session_id, title, updated_at }], sorted by updated_at desc, capped at MAX_SESSIONS_LIST."""
        org = organization_id or "default"
        out = []
        for (o, sid), state in self._store.items():
            if o != org:
                continue
            out.append({
                "session_id": state.session_id,
                "title": state.title or "New chat",
                "updated_at": state.updated_at,
            })
        out.sort(key=lambda x: (x["updated_at"] or 0), reverse=True)
        return out[:MAX_SESSIONS_LIST]

    def set_context_summary(self, organization_id: str, session_id: str, summary: dict) -> None:
        self.get_or_create_session(organization_id, session_id).context_summary = summary

    def get_context_summary(self, organization_id: str, session_id: str) -> Optional[dict]:
        state = self._store.get(self._key(organization_id, session_id))
        return state.context_summary if state else None

    def clear_session(self, organization_id: str, session_id: str) -> bool:
        key = self._key(organization_id, session_id)
        if key in self._store:
            del self._store[key]
            return True
        return False


_session_store: Optional[SessionMemoryStore] = None


def get_session_store() -> SessionMemoryStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionMemoryStore()
    return _session_store
