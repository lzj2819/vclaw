"""Tests for L1 User Interaction."""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l1_user_interaction import (
    UserInteraction, DataValidator,
    ValidationError
)
from src.models import StandardEvent


class TestUserInteraction:
    """Tests for L1 User Interaction."""
    
    def test_telegram_message_normalization(self):
        """TC-L1-001: Telegram消息标准化"""
        # Arrange
        interaction = UserInteraction()
        
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
        
        # Act
        event = interaction.receive_payload(raw_data, channel="telegram")
        
        # Assert
        assert event.channel == "telegram"
        assert event.user_id == "12345"
        assert event.content == "Hello bot"
        assert event.timestamp == 1234567890
    
    def test_validation_failure(self):
        """TC-L1-002: 数据验证失败"""
        # Arrange
        interaction = UserInteraction()
        
        raw_data = {
            # Missing required fields
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            interaction.receive_payload(raw_data, channel="telegram")
    
    def test_websocket_message_processing(self):
        """TC-L1-003: WebSocket消息处理"""
        # Arrange
        interaction = UserInteraction()
        
        raw_data = {
            "type": "message",
            "user_id": "ws_user_123",
            "content": "WebSocket test",
            "timestamp": 1234567890
        }
        
        # Act
        event = interaction.receive_payload(raw_data, channel="websocket")
        
        # Assert
        assert event.channel == "websocket"
        assert event.user_id == "ws_user_123"
        assert event.content == "WebSocket test"


class TestDataValidator:
    """Tests for data validation."""
    
    def test_valid_data(self):
        """Test validation with valid data"""
        from src.l1_user_interaction import DataValidator
        
        validator = DataValidator()
        data = {
            "channel": "telegram",
            "user_id": "12345",
            "content": "Hello",
            "timestamp": 1234567890
        }
        
        assert validator.validate(data) is True
    
    def test_missing_required_field(self):
        """Test validation with missing field"""
        from src.l1_user_interaction import DataValidator
        
        validator = DataValidator()
        data = {
            "channel": "telegram",
            # Missing user_id
            "content": "Hello",
            "timestamp": 1234567890
        }
        
        with pytest.raises(ValidationError):
            validator.validate(data)
