"""Tests for L5 Tools & Capabilities."""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l5_tools import (
    ToolsCapabilities, ToolNotFoundError, 
    ValidationError, PermissionDeniedError
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
            # Act
            result = tools.execute(
                "python_repl",
                {"code": "print(1+1)"},
                user_permissions=["admin"],
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
                user_permissions=["admin"]
            )
    
    def test_permission_denied(self):
        """TC-L5-003: 权限不足被拒绝"""
        # Arrange
        tools = ToolsCapabilities()
        
        # Act & Assert
        with pytest.raises(PermissionDeniedError):
            tools.execute(
                "python_repl",
                {"code": "print('hello')"},
                user_permissions=["guest"]  # Guest cannot execute code
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
                user_permissions=["admin"]
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
                    user_permissions=["admin"],
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
                user_permissions=["admin"]
            )
            
            # Assert
            assert len(result.result) <= 10000
            assert result.metadata.get("truncated") is True
    
    def test_get_available_tools(self):
        """TC-L5-007: 获取可用工具列表"""
        # Arrange
        tools = ToolsCapabilities()
        
        # Act
        available = tools.get_available_tools(["user"])
        
        # Assert
        assert isinstance(available, list)
        # Should only include tools user has permission for
        tool_names = [t.get("function", {}).get("name") for t in available]
        assert "calculator" in tool_names  # User can use calculator
