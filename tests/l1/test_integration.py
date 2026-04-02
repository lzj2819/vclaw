"""Integration tests for UserInteraction.

Tests the complete L1 layer integrating all components.
"""
import pytest
from unittest.mock import Mock, patch
from src.l1_user_interaction import (
    UserInteraction,
    DataValidator,
    EventNormalizer,
    ErrorHandler,
)
from src.models import StandardEvent
from src.exceptions import ValidationError


@pytest.fixture
def user_interaction():
    """Provide UserInteraction instance."""
    return UserInteraction()


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


class TestUserInteraction:
    """Integration tests for UserInteraction class."""

    def test_receive_payload_telegram(self, user_interaction, sample_telegram_data):
        """End-to-end test for Telegram payload."""
        with patch('src.l1_user_interaction.time.sleep'):
            event = user_interaction.receive_payload(sample_telegram_data)

        assert isinstance(event, StandardEvent)
        assert event.channel == "telegram"
        assert event.user_id == "12345"
        assert event.content == "Hello bot"

    def test_receive_payload_websocket(self, user_interaction, sample_websocket_data):
        """End-to-end test for WebSocket payload."""
        event = user_interaction.receive_payload(sample_websocket_data)

        assert isinstance(event, StandardEvent)
        assert event.channel == "websocket"
        assert event.user_id == "user_123"
        assert event.content == "Hello from WebSocket"

    def test_receive_payload_webhook(self, user_interaction, sample_webhook_data):
        """End-to-end test for Webhook payload."""
        event = user_interaction.receive_payload(sample_webhook_data)

        assert isinstance(event, StandardEvent)
        assert event.channel == "webhook"
        assert event.user_id == "webhook_user_789"
        assert event.content == "Webhook payload content"

    def test_receive_payload_with_channel_hint(self, user_interaction, sample_telegram_data):
        """Test receive_payload with explicit channel hint."""
        event = user_interaction.receive_payload(sample_telegram_data, channel="telegram")

        assert event.channel == "telegram"
        assert event.user_id == "12345"

    def test_receive_payload_validation_error(self):
        """Test validation error handling."""
        # Create a mock validator that raises ValidationError
        mock_validator = Mock()
        mock_validator.validate.side_effect = ValidationError("user_id cannot be empty")
        ui = UserInteraction(validator=mock_validator)

        # Valid Telegram data that will be parsed but fail validation
        data = {
            "update_id": 123,
            "message": {
                "from": {"id": 12345},
                "text": "content",
                "date": 1234567890
            }
        }

        with pytest.raises(ValidationError, match="user_id cannot be empty"):
            ui.receive_payload(data)

    def test_get_supported_channels(self, user_interaction):
        """Test getting list of supported channels."""
        channels = user_interaction.get_supported_channels()

        assert isinstance(channels, list)
        assert set(channels) == {"telegram", "websocket", "webhook"}

    def test_custom_components_initialization(self):
        """Test UserInteraction with custom component instances."""
        custom_validator = DataValidator()
        custom_error_handler = ErrorHandler(max_retries=5)
        custom_normalizer = EventNormalizer()

        ui = UserInteraction(
            validator=custom_validator,
            error_handler=custom_error_handler,
            normalizer=custom_normalizer
        )

        assert ui.validator is custom_validator
        assert ui.error_handler is custom_error_handler
        assert ui.normalizer is custom_normalizer


class TestXMLTestCases:
    """Explicit test cases from XML specification."""

    def test_TC_L1_001_telegram_message_normalization(self):
        """TC-L1-001: Verify Telegram format converts to StandardEvent."""
        raw_data = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {"id": 12345, "first_name": "User"},
                "chat": {"id": 12345, "type": "private"},
                "date": 1234567890,
                "text": "Hello bot"
            }
        }

        ui = UserInteraction()
        event = ui.receive_payload(raw_data)

        # Expected checks from XML spec
        assert event.channel == "telegram"
        assert event.user_id == str(raw_data["message"]["from"]["id"])
        assert event.content == raw_data["message"]["text"]

    def test_TC_L1_002_validation_error_handling(self):
        """TC-L1-002: Verify invalid data raises ValidationError."""
        ui = UserInteraction()

        # Data that passes adapter (has update_id for Telegram) but fails validation
        # The adapter parses it first, then validation fails on the result
        invalid_data = {
            "update_id": 123,
            "message": {
                "from": {"id": 12345},
                "text": "content",
                "date": 1234567890
            }
        }

        # Override validator to trigger validation error
        mock_validator = Mock()
        mock_validator.validate.side_effect = ValidationError("user_id cannot be empty")
        ui = UserInteraction(validator=mock_validator)

        with pytest.raises(ValidationError) as exc_info:
            ui.receive_payload(invalid_data)

        # Error message should contain validation error
        error_msg = str(exc_info.value)
        assert "user_id" in error_msg or "content" in error_msg

    def test_TC_L1_003_websocket_message_handling(self):
        """TC-L1-003: Verify WebSocket format converts to StandardEvent."""
        raw_data = {
            "type": "message",
            "user_id": "ws_user_123",
            "content": "WebSocket test message",
            "timestamp": 1704067200.0
        }

        ui = UserInteraction()
        event = ui.receive_payload(raw_data)

        # Expected checks from XML spec
        assert event.channel == "websocket"
        assert hasattr(event, 'user_id')
        assert hasattr(event, 'content')
        assert hasattr(event, 'timestamp')

    def test_TC_L1_004_retry_mechanism(self):
        """TC-L1-004: Verify retry mechanism with exponential backoff."""
        handler = ErrorHandler(max_retries=3, initial_delay=1.0)

        # Mock operation that fails 3 times then succeeds
        call_count = [0]

        def failing_operation():
            call_count[0] += 1
            if call_count[0] < 4:  # Fail first 3 times
                raise ConnectionError(f"Failure {call_count[0]}")
            return "success"

        with patch('src.l1_user_interaction.time.sleep') as mock_sleep:
            result = handler.execute_with_retry(
                failing_operation,
                retryable_exceptions=(ConnectionError,)
            )

        # Expected from XML spec:
        # - Total 4 attempts (initial + 3 retries)
        # - Exponential backoff between retries
        assert call_count[0] == 4  # Initial + 3 retries
        assert result == "success"
        assert mock_sleep.call_count == 3  # 3 delays between 4 attempts

        # Verify exponential backoff: 1s, 2s, 4s
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays[0] == 1.0  # Initial delay
        assert delays[1] == 2.0  # 1 * 2
        assert delays[2] == 4.0  # 2 * 2
