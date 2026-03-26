"""L2: Control Gateway Layer - Authentication, rate limiting, session management."""
import time
import uuid
from typing import Dict, List, Optional
from collections import defaultdict, deque
from src.models import StandardEvent, SessionContext
from src.interfaces import MemoryInterface
from src.l4_memory import MemoryKnowledge


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class ForbiddenError(Exception):
    """Raised when user lacks permission."""
    pass


class SessionError(Exception):
    """Raised when session operation fails."""
    pass


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


class Authenticator:
    """Simple authenticator."""
    
    def verify_token(self, token: str) -> bool:
        """Verify authentication token."""
        # Mock implementation - accept any non-empty token
        return bool(token) and token != "invalid_token"
    
    def get_user_permissions(self, user_id: str) -> List[str]:
        """Get user permissions."""
        # Mock implementation
        if user_id.startswith("admin"):
            return ["admin", "user"]
        elif user_id.startswith("guest"):
            return ["guest"]
        return ["user"]


class ControlGateway:
    """L2 implementation - Control gateway."""
    
    def __init__(self, memory: MemoryInterface = None):
        self.memory = memory or MemoryKnowledge()
        self.rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
        self.authenticator = Authenticator()
        self.sessions = {}  # session_id -> session_data
    
    def process_event(self, event: StandardEvent) -> SessionContext:
        """Process event and create session context."""
        # Check rate limit
        if not self.rate_limiter.is_allowed(event.user_id):
            raise RateLimitExceeded(f"Rate limit exceeded for user {event.user_id}")
        
        # Authenticate
        token = event.metadata.get("auth_token")
        if token and not self.authenticator.verify_token(token):
            raise AuthenticationError("Invalid authentication token")
        
        # Get user permissions
        user_permissions = self.authenticator.get_user_permissions(event.user_id)
        
        # Check required permission if specified
        required_perm = event.metadata.get("required_permission")
        if required_perm and required_perm not in user_permissions:
            raise ForbiddenError(f"Permission '{required_perm}' required")
        
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
            user_permissions=user_permissions,
            metadata={"channel": event.channel}
        )
        
        return context
    
    def send_response(self, session_id: str, text: str) -> bool:
        """Send response to user."""
        # Mock implementation - just log
        print(f"[L2] Sending response to session {session_id}: {text[:50]}...")
        return True
