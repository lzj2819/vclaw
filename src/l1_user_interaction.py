"""L1: User Interaction Layer - Handle external inputs."""
from typing import Dict, Any
from src.models import StandardEvent


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


class UnsupportedChannelError(Exception):
    """Raised when channel is not supported."""
    pass


class DataValidator:
    """Data validator."""
    
    REQUIRED_FIELDS = ["channel", "user_id", "content"]
    
    def validate(self, data: Dict) -> bool:
        """Validate raw data."""
        for field in self.REQUIRED_FIELDS:
            if field not in data or not data[field]:
                raise ValidationError(f"Missing required field: {field}")
        return True


class EventNormalizer:
    """Event normalizer."""
    
    def normalize(self, raw_data: Dict, channel: str) -> StandardEvent:
        """Normalize raw data to StandardEvent."""
        if channel == "telegram":
            return self._normalize_telegram(raw_data)
        elif channel == "websocket":
            return self._normalize_websocket(raw_data)
        elif channel == "webhook":
            return self._normalize_webhook(raw_data)
        else:
            raise UnsupportedChannelError(f"Channel '{channel}' not supported")
    
    def _normalize_telegram(self, data: Dict) -> StandardEvent:
        """Normalize Telegram data."""
        message = data.get("message", {})
        from_user = message.get("from", {})
        
        return StandardEvent(
            channel="telegram",
            user_id=str(from_user.get("id", "")),
            content=message.get("text", ""),
            timestamp=message.get("date", 0.0),
            metadata={
                "chat_id": message.get("chat", {}).get("id"),
                "message_id": message.get("message_id")
            }
        )
    
    def _normalize_websocket(self, data: Dict) -> StandardEvent:
        """Normalize WebSocket data."""
        return StandardEvent(
            channel="websocket",
            user_id=str(data.get("user_id", "")),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", 0.0),
            metadata={"type": data.get("type", "message")}
        )
    
    def _normalize_webhook(self, data: Dict) -> StandardEvent:
        """Normalize Webhook data."""
        return StandardEvent(
            channel="webhook",
            user_id=str(data.get("user_id", "")),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", 0.0),
            metadata={"headers": data.get("headers", {})}
        )


class UserInteraction:
    """L1 implementation - User interaction layer."""
    
    SUPPORTED_CHANNELS = {"telegram", "websocket", "webhook"}
    
    def __init__(self):
        self.validator = DataValidator()
        self.normalizer = EventNormalizer()
    
    def receive_payload(self, raw_data: Dict, channel: str = None) -> StandardEvent:
        """Receive and process payload from any channel."""
        # Detect channel if not provided
        if not channel:
            channel = self._detect_channel(raw_data)
        
        # Validate channel
        if channel not in self.SUPPORTED_CHANNELS:
            raise UnsupportedChannelError(f"Channel '{channel}' not supported")
        
        # Normalize to StandardEvent
        event = self.normalizer.normalize(raw_data, channel)
        
        # Validate
        self.validator.validate(event.model_dump())
        
        return event
    
    def _detect_channel(self, raw_data: Dict) -> str:
        """Auto-detect channel from data format."""
        if "update_id" in raw_data or "message" in raw_data:
            return "telegram"
        elif "type" in raw_data:
            return "websocket"
        else:
            return "webhook"
