"""Tests for ProtocolAdapter implementations.

TC-L1-001: Telegram message normalization
TC-L1-003: WebSocket message handling
"""
import pytest
from src.l1_user_interaction import (
    TelegramAdapter,
    WebSocketAdapter,
    HttpWebhookAdapter,
)
from src.models import StandardEvent
from src.exceptions import ParseError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def telegram_adapter():
    """Provide TelegramAdapter instance."""
    return TelegramAdapter()


@pytest.fixture
def websocket_adapter():
    """Provide WebSocketAdapter instance."""
    return WebSocketAdapter()


@pytest.fixture
def webhook_adapter():
    """Provide HttpWebhookAdapter instance."""
    return HttpWebhookAdapter()


@pytest.fixture
def sample_telegram_data():
    """Provide sample Telegram update data."""
    return {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {"id": 12345, "first_name": "TestUser", "username": "testuser"},
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
        "headers": {"X-Signature": "abc123", "Content-Type": "application/json"},
        "user_id": "webhook_user_789",
        "content": "Webhook payload content",
        "timestamp": 1704067200.0,
        "webhook_type": "incoming_message"
    }


# =============================================================================
# TelegramAdapter Tests
# =============================================================================

class TestTelegramAdapter:
    """Test cases for TelegramAdapter - TC-L1-001."""

    def test_can_handle_telegram_data(self, telegram_adapter, sample_telegram_data):
        """Test TelegramAdapter correctly identifies Telegram data."""
        assert telegram_adapter.can_handle(sample_telegram_data) is True

    def test_can_handle_non_telegram_data(self, telegram_adapter):
        """Test TelegramAdapter correctly rejects non-Telegram data."""
        non_telegram_data = {"type": "message", "user_id": "123"}
        assert telegram_adapter.can_handle(non_telegram_data) is False

    def test_parse_valid_telegram_data(self, telegram_adapter, sample_telegram_data):
        """Test parsing valid Telegram data into StandardEvent - TC-L1-001."""
        event = telegram_adapter.parse(sample_telegram_data)

        assert isinstance(event, StandardEvent)
        assert event.channel == "telegram"
        assert event.user_id == "12345"
        assert event.content == "Hello bot"
        assert event.timestamp == 1704067200.0
        assert event.metadata["chat_id"] == 12345
        assert event.metadata["first_name"] == "TestUser"
        assert event.metadata["username"] == "testuser"

    def test_parse_missing_user_id(self, telegram_adapter):
        """Test ParseError raised when user_id is missing."""
        invalid_data = {
            "update_id": 123,
            "message": {
                "text": "Hello",
                "date": 1234567890
            }
        }
        with pytest.raises(ParseError, match="missing user_id"):
            telegram_adapter.parse(invalid_data)

    def test_parse_missing_content(self, telegram_adapter):
        """Test ParseError raised when content is missing."""
        invalid_data = {
            "update_id": 123,
            "message": {
                "from": {"id": 12345},
                "date": 1234567890
            }
        }
        with pytest.raises(ParseError, match="missing content"):
            telegram_adapter.parse(invalid_data)

    def test_get_channel_name(self, telegram_adapter):
        """Test channel name is 'telegram'."""
        assert telegram_adapter.get_channel_name() == "telegram"


# =============================================================================
# WebSocketAdapter Tests
# =============================================================================

class TestWebSocketAdapter:
    """Test cases for WebSocketAdapter - TC-L1-003."""

    def test_can_handle_websocket_data(self, websocket_adapter, sample_websocket_data):
        """Test WebSocketAdapter correctly identifies WebSocket data."""
        assert websocket_adapter.can_handle(sample_websocket_data) is True

    def test_can_handle_non_websocket_data(self, websocket_adapter):
        """Test WebSocketAdapter correctly rejects non-WebSocket data."""
        non_ws_data = {"update_id": 123, "message": {}}
        assert websocket_adapter.can_handle(non_ws_data) is False

    def test_parse_valid_websocket_data(self, websocket_adapter, sample_websocket_data):
        """Test parsing valid WebSocket data into StandardEvent - TC-L1-003."""
        event = websocket_adapter.parse(sample_websocket_data)

        assert isinstance(event, StandardEvent)
        assert event.channel == "websocket"
        assert event.user_id == "user_123"
        assert event.content == "Hello from WebSocket"
        assert event.timestamp == 1704067200.0
        assert event.metadata["type"] == "message"
        assert event.metadata["connection_id"] == "conn_456"

    def test_parse_with_message_field(self, websocket_adapter):
        """Test parsing when content is in 'message' field."""
        data = {
            "type": "message",
            "user_id": "user_123",
            "message": "Alternative content field"
        }
        event = websocket_adapter.parse(data)
        assert event.content == "Alternative content field"

    def test_parse_missing_user_id(self, websocket_adapter):
        """Test ParseError raised when user_id is missing."""
        invalid_data = {"type": "message", "content": "Hello"}
        with pytest.raises(ParseError, match="missing user_id"):
            websocket_adapter.parse(invalid_data)

    def test_get_channel_name(self, websocket_adapter):
        """Test channel name is 'websocket'."""
        assert websocket_adapter.get_channel_name() == "websocket"


# =============================================================================
# HttpWebhookAdapter Tests
# =============================================================================

class TestHttpWebhookAdapter:
    """Test cases for HttpWebhookAdapter."""

    def test_can_handle_webhook_data_with_headers(self, webhook_adapter, sample_webhook_data):
        """Test HttpWebhookAdapter identifies data with headers."""
        assert webhook_adapter.can_handle(sample_webhook_data) is True

    def test_can_handle_webhook_data_with_type(self, webhook_adapter):
        """Test HttpWebhookAdapter identifies data with webhook_type."""
        data = {"webhook_type": "notification", "user_id": "123", "content": "test"}
        assert webhook_adapter.can_handle(data) is True

    def test_can_handle_non_webhook_data(self, webhook_adapter):
        """Test HttpWebhookAdapter correctly rejects non-webhook data."""
        non_webhook_data = {"update_id": 123, "message": {}}
        assert webhook_adapter.can_handle(non_webhook_data) is False

    def test_parse_valid_webhook_data(self, webhook_adapter, sample_webhook_data):
        """Test parsing valid Webhook data into StandardEvent."""
        event = webhook_adapter.parse(sample_webhook_data)

        assert isinstance(event, StandardEvent)
        assert event.channel == "webhook"
        assert event.user_id == "webhook_user_789"
        assert event.content == "Webhook payload content"
        assert event.metadata["webhook_type"] == "incoming_message"
        assert event.metadata["signature"] == "abc123"

    def test_get_channel_name(self, webhook_adapter):
        """Test channel name is 'webhook'."""
        assert webhook_adapter.get_channel_name() == "webhook"
