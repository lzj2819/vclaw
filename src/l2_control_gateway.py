"""L2: Control Gateway Layer - Rate limiting, session management."""
import time
import uuid
from typing import Dict, List, Optional
from collections import defaultdict, deque
from src.models import StandardEvent, SessionContext
from src.interfaces import MemoryInterface
from src.l4_memory import MemoryKnowledge
from src.exceptions import (
    RateLimitExceeded, SessionError,
    AuthenticationError, ForbiddenError  # Deprecated but kept for compatibility
)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)  # user_id -> deque of timestamps

    def is_allowed(self, user_id: str) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()
        user_requests = self.requests[user_id]

        # Remove old requests outside window
        while user_requests and user_requests[0] < now - self.window_seconds:
            user_requests.popleft()

        # Check if under limit
        if len(user_requests) < self.max_requests:
            user_requests.append(now)
            return True

        return False


class ControlGateway:
    """L2 implementation - Control gateway."""

    DEFAULT_SESSION_MAX_AGE = 3600  # 1 hour
    SESSION_CLEANUP_INTERVAL = 100  # Cleanup every 100 requests

    def __init__(self, memory: MemoryInterface = None,
                 session_max_age: int = DEFAULT_SESSION_MAX_AGE):
        self.memory = memory or MemoryKnowledge()
        self.rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
        self.sessions = {}  # session_id -> session_data
        self.session_max_age = session_max_age
        self._request_count = 0

    def _cleanup_expired_sessions(self):
        """Remove expired sessions to prevent memory leaks."""
        now = time.time()
        expired = [
            sid for sid, data in self.sessions.items()
            if now - data.get("created_at", 0) > self.session_max_age
        ]
        for sid in expired:
            del self.sessions[sid]

    def process_event(self, event: StandardEvent) -> SessionContext:
        """Process event and create session context."""
        # Periodic cleanup of expired sessions
        self._request_count += 1
        if self._request_count >= self.SESSION_CLEANUP_INTERVAL:
            self._cleanup_expired_sessions()
            self._request_count = 0

        # Check rate limit
        if not self.rate_limiter.is_allowed(event.user_id):
            raise RateLimitExceeded(f"Rate limit exceeded for user {event.user_id}")

        # Get or create session
        session_id = event.metadata.get("session_id")
        if not session_id or session_id not in self.sessions:
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {
                "user_id": event.user_id,
                "created_at": time.time()
            }

        # Retrieve history
        history = self.memory.retrieve_history(session_id, limit=10)

        # Create context
        context = SessionContext(
            session_id=session_id,
            user_id=event.user_id,
            current_query=event.content,
            history=history,
            user_permissions=[],  # Empty permissions - auth removed
            metadata={"channel": event.channel}
        )

        return context

    def send_response(self, session_id: str, text: str) -> bool:
        """Send response to user."""
        # Mock implementation - just log
        print(f"[L2] Sending response to session {session_id}: {text[:50]}...")
        return True
