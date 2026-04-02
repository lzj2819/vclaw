"""Tests for EventNormalizer.

Converts raw data from various channels to StandardEvent format.
"""
import pytest
from src.l1_user_interaction import EventNormalizer, TelegramAdapter
from src.models import StandardEvent
from src.exceptions import UnsupportedChannelError


@pytest.fixture
def normalizer():
    """Provide EventNormalizer instance."""
    return EventNormalizer()


@pytest.fixture
def sample_telegram_data():
    """Provide sample Telegram update data."""
    return {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {"id": 12345, "first_name": "TestUser"},
            "chat": {"id": 12345, "type": "private"},
            "date": 1704067200,
            "text": "Hello bot"
        }
    }


@pytest.fixture
def sample_websocket_data():
    """Provide sample WebSocket message data."""
    return {
        "type": "message",
        "user_id": "user_123",
        "content": "Hello from WebSocket",
        "timestamp": 1704067200.0,
        "connection_id": "conn_456"
    }


@pytest.fixture
def sample_webhook_data():
    """Provide sample HTTP Webhook data."""
    return {
        "headers": {"X-Signature": "abc123"},
        "user_id": "webhook_user_789",
        "content": "Webhook payload content",
        "timestamp": 1704067200.0,
        "webhook_type": "incoming_message"
    }


class TestEventNormalizer:
    """Test cases for EventNormalizer."""

    def test_normalize_telegram_auto_detect(self, normalizer, sample_telegram_data):
        """Test auto-detection and normalization of Telegram data."""
        event = normalizer.normalize(sample_telegram_data)

        assert event.channel == "telegram"
        assert event.user_id == "12345"
        assert event.content == "Hello bot"

    def test_normalize_websocket_auto_detect(self, normalizer, sample_websocket_data):
        """Test auto-detection and normalization of WebSocket data."""
        event = normalizer.normalize(sample_websocket_data)

        assert event.channel == "websocket"
        assert event.user_id == "user_123"
        assert event.content == "Hello from WebSocket"

    def test_normalize_webhook_auto_detect(self, normalizer, sample_webhook_data):
        """Test auto-detection and normalization of Webhook data."""
        event = normalizer.normalize(sample_webhook_data)

        assert event.channel == "webhook"
        assert event.user_id == "webhook_user_789"

    def test_normalize_with_channel_hint(self, normalizer, sample_telegram_data):
        """Test normalization with explicit channel hint."""
        event = normalizer.normalize(sample_telegram_data, channel="telegram")

        assert event.channel == "telegram"
        assert event.user_id == "12345"

    def test_normalize_unsupported_channel(self, normalizer):
        """Test UnsupportedChannelError for invalid channel hint."""
        with pytest.raises(UnsupportedChannelError, match="No adapter found"):
            normalizer.normalize({"user_id": "123", "content": "test"}, channel="unknown")

    def test_normalize_no_adapter_can_handle(self, normalizer):
        """Test UnsupportedChannelError when no adapter can handle data."""
        invalid_data = {"unknown_field": "value"}
        with pytest.raises(UnsupportedChannelError, match="No adapter can handle"):
            normalizer.normalize(invalid_data)

    def test_normalize_with_custom_adapters(self):
        """Test EventNormalizer with custom adapter list."""
        custom_adapter = TelegramAdapter()
        normalizer = EventNormalizer(adapters=[custom_adapter])

        assert len(normalizer.adapters) == 1
        assert normalizer.adapters[0] == custom_adapter

    def test_normalize_returns_standard_event(self, normalizer, sample_telegram_data):
        """Test normalize returns StandardEvent instance."""
        event = normalizer.normalize(sample_telegram_data)

        assert isinstance(event, StandardEvent)
        assert hasattr(event, 'channel')
        assert hasattr(event, 'user_id')
        assert hasattr(event, 'content')
        assert hasattr(event, 'timestamp')
        assert hasattr(event, 'metadata')
