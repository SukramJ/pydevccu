"""Tests for SessionManager."""

from __future__ import annotations

import time

from pydevccu.session import SessionManager


class TestSessionLogin:
    """Test login functionality."""

    def test_login_success(self, session_manager: SessionManager) -> None:
        """Test successful login."""
        session_id = session_manager.login("Admin", "test123")
        assert session_id is not None
        assert len(session_id) == 32

    def test_login_wrong_password(self, session_manager: SessionManager) -> None:
        """Test login with wrong password."""
        session_id = session_manager.login("Admin", "wrong")
        assert session_id is None

    def test_login_wrong_username(self, session_manager: SessionManager) -> None:
        """Test login with wrong username."""
        session_id = session_manager.login("Wrong", "test123")
        assert session_id is None


class TestSessionLogout:
    """Test logout functionality."""

    def test_logout_success(self, session_manager: SessionManager) -> None:
        """Test successful logout."""
        session_id = session_manager.login("Admin", "test123")
        assert session_id is not None

        result = session_manager.logout(session_id)
        assert result is True

        # Session should be invalid now
        assert session_manager.validate(session_id) is False

    def test_logout_invalid_session(self, session_manager: SessionManager) -> None:
        """Test logout with invalid session."""
        result = session_manager.logout("invalid-session-id")
        assert result is False


class TestSessionValidation:
    """Test session validation."""

    def test_validate_valid_session(self, session_manager: SessionManager) -> None:
        """Test validation of valid session."""
        session_id = session_manager.login("Admin", "test123")
        assert session_id is not None
        assert session_manager.validate(session_id) is True

    def test_validate_invalid_session(self, session_manager: SessionManager) -> None:
        """Test validation of invalid session."""
        assert session_manager.validate("invalid") is False

    def test_validate_none_session(self, session_manager: SessionManager) -> None:
        """Test validation of None session."""
        assert session_manager.validate(None) is False

    def test_validate_empty_session(self, session_manager: SessionManager) -> None:
        """Test validation of empty session."""
        assert session_manager.validate("") is False

    def test_validate_updates_last_access(self, session_manager: SessionManager) -> None:
        """Test that validation updates last access time."""
        session_id = session_manager.login("Admin", "test123")
        assert session_id is not None

        session = session_manager.get_session(session_id)
        assert session is not None
        old_access = session.last_access

        time.sleep(0.01)  # Small delay
        session_manager.validate(session_id)

        session = session_manager.get_session(session_id)
        assert session is not None
        assert session.last_access > old_access


class TestSessionRenew:
    """Test session renewal."""

    def test_renew_success(self, session_manager: SessionManager) -> None:
        """Test successful session renewal."""
        session_id = session_manager.login("Admin", "test123")
        assert session_id is not None

        new_session_id = session_manager.renew(session_id)
        assert new_session_id is not None
        assert new_session_id != session_id

        # Old session should be invalid
        assert session_manager.validate(session_id) is False
        # New session should be valid
        assert session_manager.validate(new_session_id) is True

    def test_renew_invalid_session(self, session_manager: SessionManager) -> None:
        """Test renewal of invalid session."""
        result = session_manager.renew("invalid")
        assert result is None


class TestAuthEnabled:
    """Test auth enabled/disabled functionality."""

    def test_auth_enabled_by_default(self) -> None:
        """Test auth is enabled by default."""
        sm = SessionManager(auth_enabled=True)
        assert sm.auth_enabled is True

    def test_auth_disabled(self) -> None:
        """Test auth can be disabled."""
        sm = SessionManager(auth_enabled=False)
        assert sm.auth_enabled is False

    def test_validate_always_true_when_disabled(self, session_manager_no_auth: SessionManager) -> None:
        """Test validation always succeeds when auth is disabled."""
        assert session_manager_no_auth.validate(None) is True
        assert session_manager_no_auth.validate("any-value") is True
        assert session_manager_no_auth.validate("") is True


class TestSessionCount:
    """Test session counting."""

    def test_active_session_count(self, session_manager: SessionManager) -> None:
        """Test counting active sessions."""
        assert session_manager.active_session_count() == 0

        session_manager.login("Admin", "test123")
        assert session_manager.active_session_count() == 1

        session_manager.login("Admin", "test123")
        assert session_manager.active_session_count() == 2


class TestInvalidateAll:
    """Test invalidating all sessions."""

    def test_invalidate_all(self, session_manager: SessionManager) -> None:
        """Test invalidating all sessions."""
        s1 = session_manager.login("Admin", "test123")
        s2 = session_manager.login("Admin", "test123")
        assert s1 is not None
        assert s2 is not None

        count = session_manager.invalidate_all()
        assert count == 2
        assert session_manager.active_session_count() == 0


class TestGetUsername:
    """Test getting configured username."""

    def test_get_username(self, session_manager: SessionManager) -> None:
        """Test getting username."""
        assert session_manager.get_username() == "Admin"


class TestCleanupExpired:
    """Test expired session cleanup."""

    def test_cleanup_expired(self) -> None:
        """Test cleaning up expired sessions."""
        # Create manager with very short timeout
        sm = SessionManager(
            username="Admin",
            password="test",
            session_timeout=0,  # Immediate expiration
        )

        session_id = sm.login("Admin", "test")
        assert session_id is not None

        # Session should be expired immediately
        time.sleep(0.01)
        count = sm.cleanup_expired()
        assert count == 1
        assert sm.active_session_count() == 0
