"""
Session Manager — In-memory session store for field submission flows.

Each user's 9-step journey gets a session_id. The session holds accumulated
state (input, analysis, corrections, search results, selections) as
the user progresses through steps.

In production, swap this for Redis or Cosmos DB backed storage.
"""

import uuid
import time
import threading
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from .config import TEMP_STORAGE_TTL
from .models import SessionState, FlowStep, IssueSubmission

logger = logging.getLogger("field-portal.sessions")


class SessionManager:
    """Thread-safe in-memory session store with TTL expiry."""

    def __init__(self, ttl: int = TEMP_STORAGE_TTL):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl
        self._lock = threading.Lock()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def create_session(self, submission: IssueSubmission) -> SessionState:
        """Create a new session for a field submission flow."""
        session_id = str(uuid.uuid4())
        state = SessionState(
            session_id=session_id,
            current_step=FlowStep.submission,
            original_input=submission,
        )
        with self._lock:
            self._sessions[session_id] = {
                "state": state.model_dump(),
                "created_at": time.time(),
                "last_accessed": time.time(),
                # Extra data that doesn't fit in the Pydantic model
                "raw_analysis": None,         # full dict from gateway
                "raw_search_results": None,   # full dict from gateway
                "raw_related_uats": None,     # full list from gateway
                "tft_features_detail": [],    # full TFT feature objects
            }
        logger.info(f"Created session {session_id}")
        return state

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data, or None if not found/expired."""
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                return None
            entry["last_accessed"] = time.time()
            return entry

    def get_state(self, session_id: str) -> Optional[SessionState]:
        """Get the typed session state."""
        entry = self.get_session(session_id)
        if entry is None:
            return None
        return SessionState(**entry["state"])

    def update_state(self, session_id: str, **kwargs) -> Optional[SessionState]:
        """Update fields on the session state."""
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                return None
            entry["state"].update(kwargs)
            entry["last_accessed"] = time.time()
            return SessionState(**entry["state"])

    def set_extra(self, session_id: str, key: str, value: Any):
        """Store extra data on the session (raw gateway responses, etc.)."""
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is not None:
                entry[key] = value
                entry["last_accessed"] = time.time()

    def get_extra(self, session_id: str, key: str) -> Any:
        """Retrieve extra data from the session."""
        entry = self.get_session(session_id)
        if entry is None:
            return None
        return entry.get(key)

    def delete_session(self, session_id: str):
        """Delete a session."""
        with self._lock:
            self._sessions.pop(session_id, None)
        logger.info(f"Deleted session {session_id}")

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _cleanup_loop(self):
        """Periodically remove expired sessions."""
        while True:
            time.sleep(300)  # check every 5 minutes
            now = time.time()
            expired = []
            with self._lock:
                for sid, entry in self._sessions.items():
                    if now - entry["last_accessed"] > self._ttl:
                        expired.append(sid)
                for sid in expired:
                    del self._sessions[sid]
            if expired:
                logger.info(f"Expired {len(expired)} sessions")


# Singleton
_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
