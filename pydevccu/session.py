"""
Session management for pydevccu JSON-RPC authentication.

Provides session-based authentication compatible with CCU/OpenCCU
JSON-RPC API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import secrets
import threading
import time
from typing import Final

SESSION_TIMEOUT: Final = 1800  # 30 minutes
SESSION_ID_LENGTH: Final = 32


@dataclass
class Session:
    """Represents an authenticated user session."""

    session_id: str
    username: str
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    permissions: set[str] = field(default_factory=set)

    def is_expired(self, timeout: int = SESSION_TIMEOUT) -> bool:
        """Check if session has expired."""
        return (time.time() - self.last_access) > timeout

    def touch(self) -> None:
        """Update last access time."""
        self.last_access = time.time()

    def age(self) -> float:
        """Return session age in seconds."""
        return time.time() - self.created_at


class SessionManager:
    """
    Manages user sessions for JSON-RPC authentication.

    Thread-safe session management with configurable timeout
    and automatic cleanup of expired sessions.
    """

    def __init__(
        self,
        *,
        username: str = "Admin",
        password: str = "",
        session_timeout: int = SESSION_TIMEOUT,
        auth_enabled: bool = True,
    ) -> None:
        self._credentials: Final = (username, password)
        self._session_timeout: Final = session_timeout
        self._auth_enabled = auth_enabled
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self._auth_enabled

    @auth_enabled.setter
    def auth_enabled(self, value: bool) -> None:
        """Enable or disable authentication."""
        with self._lock:
            self._auth_enabled = value

    def login(self, username: str, password: str) -> str | None:
        """
        Authenticate user and create session.

        Args:
            username: The username to authenticate.
            password: The password to verify.

        Returns:
            Session ID if successful, None if authentication failed.

        """
        with self._lock:
            # Check credentials
            if (username, password) != self._credentials:
                return None

            # Generate unique session ID
            session_id = secrets.token_hex(SESSION_ID_LENGTH // 2)

            self._sessions[session_id] = Session(
                session_id=session_id,
                username=username,
            )

            return session_id

    def logout(self, session_id: str) -> bool:
        """
        Invalidate session.

        Args:
            session_id: The session ID to invalidate.

        Returns:
            True if session was found and removed, False otherwise.

        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def renew(self, session_id: str) -> str | None:
        """
        Renew session and return new session ID.

        OpenCCU returns a new session ID on renew.

        Args:
            session_id: The current session ID.

        Returns:
            New session ID if successful, None if session invalid/expired.

        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or session.is_expired(self._session_timeout):
                if session_id in self._sessions:
                    del self._sessions[session_id]
                return None

            # Create new session, invalidate old
            new_session_id = secrets.token_hex(SESSION_ID_LENGTH // 2)
            self._sessions[new_session_id] = Session(
                session_id=new_session_id,
                username=session.username,
                permissions=session.permissions.copy(),
            )
            del self._sessions[session_id]

            return new_session_id

    def validate(self, session_id: str | None) -> bool:
        """
        Check if session is valid and not expired.

        Args:
            session_id: The session ID to validate.

        Returns:
            True if session is valid, False otherwise.

        """
        if not self._auth_enabled:
            return True

        if not session_id:
            return False

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            if session.is_expired(self._session_timeout):
                del self._sessions[session_id]
                return False

            session.touch()
            return True

    def get_session(self, session_id: str) -> Session | None:
        """
        Get session by ID (does not update last access).

        Args:
            session_id: The session ID to look up.

        Returns:
            Session object if found and valid, None otherwise.

        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session and not session.is_expired(self._session_timeout):
                return session
            return None

    def cleanup_expired(self) -> int:
        """
        Remove expired sessions.

        Returns:
            Count of removed sessions.

        """
        with self._lock:
            expired = [sid for sid, session in self._sessions.items() if session.is_expired(self._session_timeout)]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)

    def active_session_count(self) -> int:
        """Return count of active (non-expired) sessions."""
        with self._lock:
            return sum(1 for session in self._sessions.values() if not session.is_expired(self._session_timeout))

    def invalidate_all(self) -> int:
        """
        Invalidate all sessions.

        Returns:
            Count of invalidated sessions.

        """
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def get_username(self) -> str:
        """Get configured username."""
        return self._credentials[0]
