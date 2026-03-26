"""pytest configuration and shared fixtures."""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_event():
    """Sample StandardEvent for testing."""
    from src.models import StandardEvent
    return StandardEvent(
        channel="test",
        user_id="user123",
        content="Hello world",
        metadata={}
    )


@pytest.fixture
def sample_context():
    """Sample SessionContext for testing."""
    from src.models import SessionContext
    return SessionContext(
        session_id="test-session-123",
        user_id="user123",
        current_query="Hello",
        history=[],
        user_permissions=["user"]
    )
