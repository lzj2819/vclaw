"""Tests for ErrorHandler.

TC-L1-004: Retry mechanism with exponential backoff
"""
import pytest
from unittest.mock import Mock, patch
from src.l1_user_interaction import ErrorHandler


@pytest.fixture
def error_handler():
    """Provide ErrorHandler instance."""
    return ErrorHandler()


class TestErrorHandler:
    """Test cases for ErrorHandler retry mechanism - TC-L1-004."""

    def test_execute_success_first_attempt(self, error_handler):
        """Test operation succeeds on first attempt."""
        operation = Mock(return_value="success")

        result = error_handler.execute_with_retry(operation, "arg1", kwarg1="value1")

        assert result == "success"
        assert operation.call_count == 1
        operation.assert_called_once_with("arg1", kwarg1="value1")

    def test_execute_success_after_retries(self, error_handler):
        """Test operation succeeds after retry attempts."""
        # Fail twice, then succeed
        operation = Mock(side_effect=[ConnectionError("Fail 1"), ConnectionError("Fail 2"), "success"])

        with patch('src.l1_user_interaction.time.sleep') as mock_sleep:
            result = error_handler.execute_with_retry(
                operation,
                retryable_exceptions=(ConnectionError,)
            )

        assert result == "success"
        assert operation.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    def test_exponential_backoff_timing(self, error_handler):
        """Test retry delays follow exponential backoff pattern - TC-L1-004."""
        operation = Mock(side_effect=[ConnectionError("Fail 1"), ConnectionError("Fail 2"), ConnectionError("Fail 3"), "success"])

        with patch('src.l1_user_interaction.time.sleep') as mock_sleep:
            error_handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))

        # Check exponential backoff: 1s, 2s, 4s
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(1.0)  # Initial delay
        mock_sleep.assert_any_call(2.0)  # 1 * 2
        mock_sleep.assert_any_call(4.0)  # 2 * 2

    def test_max_retries_exceeded(self, error_handler):
        """Test exception raised after max retries exceeded."""
        operation = Mock(side_effect=ConnectionError("Persistent failure"))

        with patch('src.l1_user_interaction.time.sleep'):
            with pytest.raises(ConnectionError, match="Persistent failure"):
                error_handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))

        # Initial + 3 retries = 4 total attempts
        assert operation.call_count == 4

    def test_non_retryable_exception(self, error_handler):
        """Test non-retryable exceptions are raised immediately."""
        operation = Mock(side_effect=ValueError("Invalid input"))

        with pytest.raises(ValueError, match="Invalid input"):
            error_handler.execute_with_retry(
                operation,
                retryable_exceptions=(ConnectionError,)  # ValueError not in list
            )

        # Should not retry on non-retryable exception
        assert operation.call_count == 1

    def test_custom_max_retries(self):
        """Test custom max_retries configuration."""
        handler = ErrorHandler(max_retries=5)
        operation = Mock(side_effect=ConnectionError("Fail"))

        with patch('src.l1_user_interaction.time.sleep'):
            with pytest.raises(ConnectionError):
                handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))

        # Initial + 5 retries = 6 total attempts
        assert operation.call_count == 6

    def test_custom_initial_delay(self):
        """Test custom initial_delay configuration."""
        handler = ErrorHandler(initial_delay=0.5)
        operation = Mock(side_effect=[ConnectionError("Fail"), "success"])

        with patch('src.l1_user_interaction.time.sleep') as mock_sleep:
            handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))

        mock_sleep.assert_called_once_with(0.5)

    def test_max_delay_cap(self):
        """Test delay is capped at max_delay."""
        handler = ErrorHandler(initial_delay=1.0, max_delay=3.0, max_retries=5)
        operation = Mock(side_effect=[ConnectionError("Fail")] * 7)  # All fail

        with patch('src.l1_user_interaction.time.sleep') as mock_sleep:
            with pytest.raises(ConnectionError):
                handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))

        # Delays should be: 1, 2, 3 (capped), 3 (capped), 3 (capped)
        calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert calls == [1.0, 2.0, 3.0, 3.0, 3.0]

    def test_is_retryable_true(self, error_handler):
        """Test is_retryable returns True for retryable exception."""
        assert error_handler.is_retryable(ConnectionError("test"), (ConnectionError,)) is True

    def test_is_retryable_false(self, error_handler):
        """Test is_retryable returns False for non-retryable exception."""
        assert error_handler.is_retryable(ValueError("test"), (ConnectionError,)) is False


class TestErrorHandlerConfiguration:
    """Test ErrorHandler configuration from XML spec."""

    def test_default_max_retries_is_3(self):
        """Verify default MaxRetries = 3 per XML spec."""
        handler = ErrorHandler()
        assert handler.max_retries == 3

    def test_default_initial_delay_is_1000ms(self):
        """Verify default InitialDelay = 1000ms (1.0s) per XML spec."""
        handler = ErrorHandler()
        assert handler.initial_delay == 1.0

    def test_exponential_backoff_strategy(self):
        """Verify exponential backoff strategy."""
        handler = ErrorHandler(initial_delay=1.0, max_retries=3)

        operation = Mock(side_effect=[ConnectionError()] * 3 + ["success"])

        with patch('src.l1_user_interaction.time.sleep') as mock_sleep:
            handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))

        # Verify exponential pattern: 1s, 2s, 4s
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]


class TestXMLTestCaseTC_L1_004:
    """Explicit TC-L1-004 test case from XML specification."""

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