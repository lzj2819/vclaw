"""Tests for L5 Tools & Capabilities."""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l5_tools import (
    ToolsCapabilities, ToolNotFoundError,
    ValidationError, ToolRegistry, ParameterValidator
)
from src.models import Observation


class TestToolsCapabilities:
    """Tests for L5 Tools & Capabilities."""

    def test_tool_execution_success(self):
        """TC-L5-001: 工具执行成功"""
        # Arrange
        tools = ToolsCapabilities()

        # Mock L6
        mock_result = Mock()
        mock_result.exit_code = 0
        mock_result.stdout = "2"
        mock_result.stderr = ""
        mock_result.execution_time = 0.1

        with patch.object(tools.runtime, 'run_code', return_value=mock_result):
            # Act - permissions removed
            result = tools.execute(
                "python_repl",
                {"code": "print(1+1)"},
                timeout=30
            )

            # Assert
            assert result.status == "success"
            assert "2" in result.result
            assert result.execution_time > 0

    def test_parameter_validation_failure(self):
        """TC-L5-002: 参数验证失败"""
        # Arrange
        tools = ToolsCapabilities()

        # Act & Assert
        with pytest.raises(ValidationError):
            tools.execute(
                "python_repl",
                {},  # Missing required 'code' parameter
                user_permissions=[]  # Permissions not checked but param kept for compatibility
            )

    def test_tool_not_found(self):
        """TC-L5-004: 工具不存在"""
        # Arrange
        tools = ToolsCapabilities()

        # Act & Assert
        with pytest.raises(ToolNotFoundError):
            tools.execute(
                "nonexistent_tool",
                {},
                user_permissions=[]
            )

    def test_execution_timeout(self):
        """TC-L5-005: 执行超时"""
        # Arrange
        tools = ToolsCapabilities()

        with patch.object(tools.runtime, 'run_code') as mock_run:
            from src.l6_runtime import ExecutionTimeoutError
            mock_run.side_effect = ExecutionTimeoutError("Timeout")

            # Act & Assert
            with pytest.raises(ExecutionTimeoutError):
                tools.execute(
                    "python_repl",
                    {"code": "while True: pass"},
                    user_permissions=[],
                    timeout=1
                )

    def test_result_formatting(self):
        """TC-L5-006: 结果格式化"""
        # Arrange
        tools = ToolsCapabilities()

        # Mock L6 with long output
        mock_result = Mock()
        mock_result.exit_code = 0
        mock_result.stdout = "x" * 15000  # 15KB output
        mock_result.stderr = ""
        mock_result.execution_time = 0.5

        with patch.object(tools.runtime, 'run_code', return_value=mock_result):
            # Act
            result = tools.execute(
                "python_repl",
                {"code": "print('x' * 15000)"},
                user_permissions=[]
            )

            # Assert
            assert len(result.result) <= 10000
            assert result.metadata.get("truncated") is True

    def test_get_available_tools(self):
        """TC-L5-007: 获取可用工具列表"""
        # Arrange
        tools = ToolsCapabilities()

        # Act - permissions not checked, all tools returned
        available = tools.get_available_tools([])

        # Assert
        assert isinstance(available, list)
        # All tools should be available (permissions removed)
        tool_names = [t.get("function", {}).get("name") for t in available]
        assert "calculator" in tool_names
        assert "python_repl" in tool_names  # Now available to all

    def test_no_permission_check(self):
        """TC-L5-NOPERM: 权限检查已移除，所有用户可使用所有工具"""
        # Arrange
        tools = ToolsCapabilities()

        # Mock L6
        mock_result = Mock()
        mock_result.exit_code = 0
        mock_result.stdout = "hello"
        mock_result.stderr = ""
        mock_result.execution_time = 0.1

        with patch.object(tools.runtime, 'run_code', return_value=mock_result):
            # Act - guest user (no permissions) can now execute python_repl
            result = tools.execute(
                "python_repl",
                {"code": "print('hello')"},
                user_permissions=[]  # No permissions
            )

            # Assert - should succeed without PermissionDeniedError
            assert result.status == "success"
            assert "hello" in result.result

    def test_tool_registry(self):
        """TC-L5-REGISTRY: 工具注册表功能"""
        # Arrange
        registry = ToolRegistry()

        # Act & Assert - list all tools
        tools = registry.list_tools()
        assert len(tools) > 0

        # Get specific tool
        tool = registry.get("calculator")
        assert tool is not None
        assert tool.name == "calculator"

    def test_parameter_validator_path_safety(self):
        """TC-L5-PATH: 参数验证器路径安全检查"""
        # Arrange
        validator = ParameterValidator()

        # Test dangerous paths
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\windows\\system32",
            "/etc/shadow"
        ]

        for path in dangerous_paths:
            assert validator.is_path_safe(path) is False

        # Test safe paths
        safe_paths = [
            "data/file.txt",
            "script.py",
            "subdir/document.md"
        ]

        for path in safe_paths:
            assert validator.is_path_safe(path) is True

    def test_terminal_command_validation(self):
        """TC-L5-TERMINAL: 终端命令验证"""
        # Arrange
        validator = ParameterValidator()

        # Test dangerous commands
        dangerous = [
            "rm -rf /",
            "sudo rm -rf",
            "eval('malicious')"
        ]

        for cmd in dangerous:
            assert validator.validate_terminal_command(cmd) is False

        # Test safe commands
        safe = [
            "ls -la",
            "pwd",
            "python script.py"
        ]

        for cmd in safe:
            assert validator.validate_terminal_command(cmd) is True

    def test_tool_descriptions_for_llm(self):
        """TC-L5-DESC: 工具描述格式化"""
        # Arrange
        tools = ToolsCapabilities()

        # Act
        descriptions = tools.get_tools_with_descriptions()

        # Assert
        assert "Available Tools:" in descriptions
        assert "python_repl" in descriptions
        assert "calculator" in descriptions
