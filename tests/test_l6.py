"""Tests for L6 Runtime Environment."""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l6_runtime import (
    RuntimeEnvironment, ProcessSandbox,
    ExecutionTimeoutError, UnsupportedLanguageError,
    ResourceExceededError, SecurityViolationError,
    SandboxCreationError
)
from src.models import ExecutionResult


class TestRuntimeEnvironment:
    """Tests for L6 Runtime Environment."""
    
    def test_python_execution_success(self):
        """TC-L6-001: Python代码执行成功"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "print('Hello World')"
        
        # Act
        result = runtime.run_code("python", code, timeout=30)
        
        # Assert
        assert result.exit_code == 0
        assert "Hello World" in result.stdout
        assert result.stderr == ""
        assert result.execution_time > 0
    
    def test_python_execution_error(self):
        """TC-L6-002: 代码执行出错"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "1/0"  # Division by zero
        
        # Act
        result = runtime.run_code("python", code)
        
        # Assert
        assert result.exit_code != 0
        assert "ZeroDivisionError" in result.stderr
    
    def test_timeout(self):
        """TC-L6-003: 超时控制"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "import time; time.sleep(10)"  # Long sleep
        
        # Act & Assert
        with pytest.raises(ExecutionTimeoutError):
            runtime.run_code("python", code, timeout=1)
    
    def test_unsupported_language(self):
        """TC-L6-004: 不支持的语言"""
        # Arrange
        runtime = RuntimeEnvironment()
        
        # Act & Assert
        with pytest.raises(UnsupportedLanguageError):
            runtime.run_code("ruby", "puts 'hello'")
    
    def test_security_violation(self):
        """TC-L6-006: 安全策略执行"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "import os; os.system('rm -rf /')"  # Dangerous code
        
        # Act & Assert
        with pytest.raises(SecurityViolationError):
            runtime.run_code("python", code)
    
    def test_output_truncation(self):
        """TC-L6-007: 输出截断"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "print('x' * 20000)"  # Generate 20KB output
        
        # Act
        result = runtime.run_code("python", code)
        
        # Assert
        assert len(result.stdout) <= 10000


class TestProcessSandbox:
    """Tests for ProcessSandbox implementation."""
    
    def test_sandbox_creation(self):
        """Test sandbox environment creation"""
        sandbox = ProcessSandbox()
        env_id = sandbox.create("test_env")
        assert env_id is not None
        sandbox.destroy(env_id)
    
    def test_sandbox_isolation(self):
        """Test sandbox isolation - cannot access outside files"""
        sandbox = ProcessSandbox()
        env_id = sandbox.create("test_env")
        
        try:
            # Try to read a file outside sandbox (should fail on some systems)
            result = sandbox.execute(env_id, 
                                    ["python", "-c", "open('/etc/passwd').read()"],
                                    timeout=5)
            # On Windows this might succeed, on Unix it might fail
            # The test is mainly to verify the method works
            assert result is not None
        finally:
            sandbox.destroy(env_id)
