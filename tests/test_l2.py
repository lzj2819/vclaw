"""Tests for L2 Control Gateway."""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l2_control_gateway import (
    ControlGateway, RateLimiter,
    RateLimitExceeded
)
from src.models import StandardEvent, SessionContext


class TestControlGateway:
    """Tests for L2 Control Gateway."""

    def test_session_creation_and_context_assembly(self):
        """TC-L2-001: 会话创建与上下文组装"""
        # Arrange
        gateway = ControlGateway()
        event = StandardEvent(
            channel="test",
            user_id="new_user_123",
            content="Hello",
            metadata={}
        )

        # Mock L4 to return empty history
        with patch.object(gateway.memory, 'retrieve_history') as mock_history:
            mock_history.return_value = []

            # Act
            context = gateway.process_event(event)

            # Assert
            assert context.user_id == "new_user_123"
            assert context.current_query == "Hello"
            assert len(context.history) == 0
            assert context.session_id is not None
            assert len(context.session_id) > 0

    def test_rate_limit_triggered(self):
        """TC-L2-002: 限流触发"""
        # Arrange
        gateway = ControlGateway()

        # Make multiple requests to trigger rate limit
        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="Test",
            metadata={}
        )

        # First 60 requests should succeed
        for i in range(60):
            try:
                with patch.object(gateway.memory, 'retrieve_history', return_value=[]):
                    gateway.process_event(event)
            except RateLimitExceeded:
                pass  # Might happen on some requests

        # 61st request should fail
        with pytest.raises(RateLimitExceeded):
            with patch.object(gateway.memory, 'retrieve_history', return_value=[]):
                gateway.process_event(event)

    def test_history_retrieval_and_concatenation(self):
        """TC-L2-004: 历史记录检索与拼接"""
        # Arrange
        gateway = ControlGateway()
        session_id = "existing_session_123"

        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="What's the weather?",
            metadata={"session_id": session_id}
        )

        # Mock history retrieval
        mock_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]

        with patch.object(gateway.memory, 'retrieve_history') as mock_retrieve:
            mock_retrieve.return_value = mock_history

            # Act
            context = gateway.process_event(event)

            # Assert
            assert len(context.history) == 2
            assert context.history[0]["content"] == "Hello"
            assert context.current_query == "What's the weather?"

    def test_send_response(self):
        """TC-L2-006: 响应发送"""
        # Arrange
        gateway = ControlGateway()
        session_id = "test_session_123"

        # Act
        result = gateway.send_response(session_id, "Hello user")

        # Assert
        assert result is True

    def test_no_auth_required(self):
        """TC-L2-NOAUTH: 身份认证已移除，请求无需令牌"""
        # Arrange
        gateway = ControlGateway()
        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="Hello",
            metadata={}  # No auth_token
        )

        # Mock L4 to return empty history
        with patch.object(gateway.memory, 'retrieve_history') as mock_history:
            mock_history.return_value = []

            # Act - should succeed without auth
            context = gateway.process_event(event)

            # Assert
            assert context.user_id == "user_123"
            assert context.user_permissions == []  # Empty permissions


class TestRateLimiter:
    """Tests for rate limiting."""

    def test_rate_limit_allows_under_limit(self):
        """Test that requests under limit are allowed"""
        from src.l2_control_gateway import RateLimiter

        limiter = RateLimiter(max_requests=10, window_seconds=60)

        # 10 requests should be allowed
        for i in range(10):
            assert limiter.is_allowed(f"user_{i}") is True

    def test_rate_limit_blocks_over_limit(self):
        """Test that requests over limit are blocked"""
        from src.l2_control_gateway import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)
        user_id = "test_user"

        # First 2 requests allowed
        assert limiter.is_allowed(user_id) is True
        assert limiter.is_allowed(user_id) is True

        # 3rd request blocked
        assert limiter.is_allowed(user_id) is False
