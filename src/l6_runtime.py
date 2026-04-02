"""L6: Runtime & Environment Layer - Sandbox code execution."""
import subprocess
import tempfile
import os
import signal
import time
from typing import Optional, Dict, Any
from pathlib import Path
from src.models import ExecutionResult
from src.interfaces import RuntimeInterface
from src.exceptions import (
    ExecutionTimeoutError, UnsupportedLanguageError,
    ResourceExceededError, SecurityViolationError, SandboxCreationError
)


class ProcessSandbox:
    """Process-based sandbox for code execution."""
    
    def __init__(self, base_dir: str = "/tmp/sandbox"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.environments = {}
    
    def create(self, environment_id: str) -> str:
        """Create a new sandbox environment."""
        env_path = self.base_dir / environment_id
        env_path.mkdir(exist_ok=True)
        self.environments[environment_id] = env_path
        return environment_id
    
    def destroy(self, environment_id: str) -> bool:
        """Destroy a sandbox environment."""
        if environment_id in self.environments:
            env_path = self.environments[environment_id]
            # Clean up files
            import shutil
            if env_path.exists():
                try:
                    shutil.rmtree(env_path)
                except:
                    pass
            del self.environments[environment_id]
            return True
        return False
    
    def execute(self, environment_id: str, command: list, 
                timeout: int = 30) -> ExecutionResult:
        """Execute a command in the sandbox."""
        env_path = self.environments.get(environment_id)
        if not env_path:
            raise SandboxCreationError(f"Environment {environment_id} not found")
        
        start_time = time.time()
        try:
            result = subprocess.run(
                command,
                cwd=env_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                exit_code=result.returncode,
                stdout=result.stdout[:10000],  # Truncate
                stderr=result.stderr[:10000],
                execution_time=execution_time,
                resource_usage={}
            )
        except subprocess.TimeoutExpired:
            raise ExecutionTimeoutError(f"Execution timed out after {timeout}s")


class RuntimeEnvironment(RuntimeInterface):
    """L6 implementation - Runtime environment management."""
    
    SUPPORTED_LANGUAGES = {"python", "javascript", "bash"}
    FORBIDDEN_PATTERNS = ["os.system", "subprocess", "__import__", "eval(", "exec("]
    
    def __init__(self):
        self.sandbox = ProcessSandbox()
    
    def run_code(self, language: str, code: str, timeout: int = 30,
                 environment_config: Optional[Dict] = None) -> ExecutionResult:
        """Execute code in sandbox."""
        # Validate language
        if language not in self.SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(f"Language {language} not supported")
        
        # Security check
        self._check_security(code)
        
        # Create sandbox
        import uuid
        env_id = self.sandbox.create(f"env_{uuid.uuid4().hex[:8]}")
        
        try:
            # Write code to file
            if language == "python":
                file_path = self.sandbox.environments[env_id] / "script.py"
                file_path.write_text(code, encoding='utf-8')
                command = ["python", str(file_path)]
            elif language == "javascript":
                file_path = self.sandbox.environments[env_id] / "script.js"
                file_path.write_text(code, encoding='utf-8')
                command = ["node", str(file_path)]
            elif language == "bash":
                file_path = self.sandbox.environments[env_id] / "script.sh"
                file_path.write_text(code, encoding='utf-8')
                command = ["bash", str(file_path)]
            
            # Execute
            result = self.sandbox.execute(env_id, command, timeout)
            return result
            
        except subprocess.TimeoutExpired:
            raise ExecutionTimeoutError(f"Execution timed out after {timeout}s")
        finally:
            # Cleanup
            try:
                self.sandbox.destroy(env_id)
            except:
                pass
    
    def _check_security(self, code: str):
        """Check code for security violations."""
        for forbidden in self.FORBIDDEN_PATTERNS:
            if forbidden in code:
                raise SecurityViolationError(f"Forbidden pattern: {forbidden}")
