"""Tests for DataValidator.

TC-L1-002: Data validation failure handling
"""
import pytest
from src.l1_user_interaction import DataValidator
from src.exceptions import ValidationError


@pytest.fixture
def validator():
    """Provide DataValidator instance."""
    return DataValidator()


class TestDataValidator:
    """Test cases for DataValidator - TC-L1-002."""

    def test_validate_valid_data(self, validator):
        """Test validation passes with valid data."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "Valid content",
            "timestamp": 1704067200.0
        }
        assert validator.validate(data) is True

    def test_validate_missing_required_field_channel(self, validator):
        """Test ValidationError raised when channel is missing."""
        data = {"user_id": "user123", "content": "Hello"}
        with pytest.raises(ValidationError, match="Missing required field: channel"):
            validator.validate(data)

    def test_validate_missing_required_field_user_id(self, validator):
        """Test ValidationError raised when user_id is missing."""
        data = {"channel": "telegram", "content": "Hello"}
        with pytest.raises(ValidationError, match="Missing required field: user_id"):
            validator.validate(data)

    def test_validate_missing_required_field_content(self, validator):
        """Test ValidationError raised when content is missing."""
        data = {"channel": "telegram", "user_id": "user123"}
        with pytest.raises(ValidationError, match="Missing required field: content"):
            validator.validate(data)

    def test_validate_invalid_channel(self, validator):
        """Test ValidationError raised for invalid channel."""
        data = {"channel": "invalid_channel", "user_id": "user123", "content": "Hello"}
        with pytest.raises(ValidationError, match="Invalid channel"):
            validator.validate(data)

    def test_validate_valid_channels(self, validator):
        """Test all valid channels pass validation."""
        for channel in ["telegram", "websocket", "webhook"]:
            data = {"channel": channel, "user_id": "user123", "content": "Hello"}
            assert validator.validate(data) is True

    def test_validate_user_id_too_long(self, validator):
        """Test ValidationError when user_id exceeds 256 chars."""
        data = {
            "channel": "telegram",
            "user_id": "x" * 257,
            "content": "Hello"
        }
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            validator.validate(data)

    def test_validate_user_id_at_max_length(self, validator):
        """Test user_id at exactly 256 chars passes."""
        data = {
            "channel": "telegram",
            "user_id": "x" * 256,
            "content": "Hello"
        }
        assert validator.validate(data) is True

    def test_validate_empty_user_id(self, validator):
        """Test ValidationError for empty user_id (catched as missing required field)."""
        data = {"channel": "telegram", "user_id": "", "content": "Hello"}
        with pytest.raises(ValidationError, match="Missing required field: user_id"):
            validator.validate(data)

    def test_validate_empty_content(self, validator):
        """Test ValidationError for empty content (catched as missing required field)."""
        data = {"channel": "telegram", "user_id": "user123", "content": ""}
        with pytest.raises(ValidationError, match="Missing required field: content"):
            validator.validate(data)

    def test_validate_content_too_long(self, validator):
        """Test ValidationError when content exceeds 10KB."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "x" * 10001
        }
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            validator.validate(data)


class TestValidatorSecurity:
    """Security validation tests."""

    def test_validate_xss_injection(self, validator):
        """Test XSS script injection is detected."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "<script>alert('xss')</script>"
        }
        with pytest.raises(ValidationError, match="injection detected"):
            validator.validate(data)

    def test_validate_javascript_protocol(self, validator):
        """Test javascript: protocol injection is detected."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "javascript:alert('xss')"
        }
        with pytest.raises(ValidationError, match="injection detected"):
            validator.validate(data)

    def test_validate_event_handler_injection(self, validator):
        """Test event handler injection is detected."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": '<img onerror="alert(1)">'
        }
        with pytest.raises(ValidationError, match="injection detected"):
            validator.validate(data)

    def test_validate_template_injection(self, validator):
        """Test template injection is detected."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "Hello ${user.password}"
        }
        with pytest.raises(ValidationError, match="injection detected"):
            validator.validate(data)

    def test_validate_jsp_injection(self, validator):
        """Test JSP/ASP injection is detected."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "<% System.exit(0); %>"
        }
        with pytest.raises(ValidationError, match="injection detected"):
            validator.validate(data)


class TestValidatorTimestamp:
    """Timestamp validation tests."""

    def test_validate_invalid_timestamp_negative(self, validator):
        """Test ValidationError for negative timestamp."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "Hello",
            "timestamp": -1
        }
        with pytest.raises(ValidationError, match="valid Unix timestamp"):
            validator.validate(data)

    def test_validate_invalid_timestamp_too_large(self, validator):
        """Test ValidationError for timestamp beyond year 2100."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "Hello",
            "timestamp": 5000000000  # Year ~2128
        }
        with pytest.raises(ValidationError, match="valid Unix timestamp"):
            validator.validate(data)

    def test_validate_invalid_timestamp_non_numeric(self, validator):
        """Test ValidationError for non-numeric timestamp."""
        data = {
            "channel": "telegram",
            "user_id": "user123",
            "content": "Hello",
            "timestamp": "not-a-number"
        }
        with pytest.raises(ValidationError, match="must be a valid numeric"):
            validator.validate(data)

    def test_validate_optional_timestamp_missing(self, validator):
        """Test validation passes when timestamp is omitted."""
        data = {"channel": "telegram", "user_id": "user123", "content": "Hello"}
        assert validator.validate(data) is True
