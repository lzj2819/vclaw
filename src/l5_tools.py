"""L5: Tools & Capabilities Layer - Tool routing and execution."""
import re
from typing import List, Dict, Any, Optional, Callable
from src.models import Observation
from src.interfaces import ToolsInterface, RuntimeInterface
from src.l6_runtime import RuntimeEnvironment
from src.exceptions import (
    ToolNotFoundError, ValidationError, ExecutionTimeoutError,
    PermissionDeniedError  # Deprecated but kept for compatibility
)


class Tool:
    """Tool definition with enhanced descriptions."""

    def __init__(self, name: str, description: str,
                 parameters: Dict, required_permission: str = None,
                 handler: Callable = None):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required_permission = required_permission  # Kept for compatibility but not enforced
        self.handler = handler  # Optional custom handler


class ToolRegistry:
    """Tool registry for dynamic tool management."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register built-in tools."""
        builtins = {
            "python_repl": Tool(
                name="python_repl",
                description="Execute Python code in a sandboxed environment. Use this for calculations, data processing, or any Python programming task.",
                parameters={
                    "code": {
                        "type": "string",
                        "description": "Python code to execute. Can include multiple lines and imports.",
                        "required": True
                    }
                },
                required_permission=None
            ),
            "calculator": Tool(
                name="calculator",
                description="Perform mathematical calculations. Supports basic arithmetic, scientific functions, and complex expressions.",
                parameters={
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate (e.g., '2+2', 'sqrt(16)', 'sin(pi/2)')",
                        "required": True
                    }
                },
                required_permission=None
            ),
            "search_web": Tool(
                name="search_web",
                description="Search the web for information. Returns search results from the internet.",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                        "required": True
                    }
                },
                required_permission=None
            ),
            "file_reader": Tool(
                name="file_reader",
                description="Read content from a file. Supports text files, code files, and documents.",
                parameters={
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read",
                        "required": True
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (default: utf-8)",
                        "required": False
                    }
                },
                required_permission=None
            ),
            "file_writer": Tool(
                name="file_writer",
                description="Write content to a file. Creates the file if it doesn't exist.",
                parameters={
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write",
                        "required": True
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                        "required": True
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (default: utf-8)",
                        "required": False
                    }
                },
                required_permission=None
            ),
            "terminal": Tool(
                name="terminal",
                description="Execute terminal/shell commands. Use with caution - only safe commands are allowed.",
                parameters={
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute (e.g., 'ls -la', 'pwd')",
                        "required": True
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory for the command (default: current directory)",
                        "required": False
                    }
                },
                required_permission=None
            )
        }
        for name, tool in builtins.items():
            self._tools[name] = tool

    def register(self, name: str, tool: Tool) -> None:
        """Register a new tool."""
        self._tools[name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def clear(self) -> None:
        """Clear all tools."""
        self._tools.clear()


class ParameterValidator:
    """Parameter validator with security checks."""

    # Dangerous path patterns for directory traversal prevention
    DANGEROUS_PATH_PATTERNS = [
        r"\.\./",           # ../
        r"\.\.\\",          # ..\
        r"^/etc/",          # /etc/
        r"^/proc/",         # /proc/
        r"^/sys/",          # /sys/
        r"^/root/",         # /root/
        r"^/boot/",         # /boot/
        r"^C:\\Windows",    # Windows system
        r"%",               # Environment variable
        r"~",               # Home directory shortcut
    ]

    # Safe terminal commands (whitelist approach)
    SAFE_TERMINAL_COMMANDS = [
        "ls", "dir", "pwd", "cd", "cat", "type", "echo", "head", "tail",
        "find", "grep", "wc", "sort", "uniq", "date", "whoami", "uname",
        "python", "python3", "node", "npm", "pip", "git status", "git log",
        "mkdir", "touch", "cp", "copy", "mv", "move", "rm", "del"
    ]

    # Dangerous terminal commands
    DANGEROUS_COMMANDS = [
        "rm -rf /", "del /f /s /q", "format", "mkfs", "dd if",
        ":(){ :|:& };:",  # Fork bomb
        "shutdown", "reboot", "halt", "poweroff",
        "sudo", "su -", "passwd", "chpasswd",
        "eval"
    ]

    @staticmethod
    def validate(params: Dict, schema: Dict) -> "ValidationResult":
        """Validate parameters against schema."""
        errors = []

        for param_name, param_def in schema.items():
            # Check required fields
            if param_def.get("required", True) and param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
                continue

            if param_name not in params:
                continue

            value = params[param_name]
            expected_type = param_def.get("type")

            # Type checking
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Parameter '{param_name}' must be a string")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.append(f"Parameter '{param_name}' must be an integer")
            elif expected_type == "boolean" and not isinstance(value, bool):
                errors.append(f"Parameter '{param_name}' must be a boolean")

            # String length validation
            if expected_type == "string" and isinstance(value, str):
                max_length = param_def.get("maxLength")
                if max_length and len(value) > max_length:
                    errors.append(f"Parameter '{param_name}' exceeds max length of {max_length}")

                # Path safety check for path parameters
                if "path" in param_name.lower() or "file" in param_name.lower():
                    if not ParameterValidator.is_path_safe(value):
                        errors.append(f"Parameter '{param_name}' contains unsafe path: {value}")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    @staticmethod
    def is_path_safe(path: str) -> bool:
        """Check if a path is safe (no directory traversal)."""
        for pattern in ParameterValidator.DANGEROUS_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return False
        return True

    @staticmethod
    def sanitize_path(path: str, base_dir: str = ".") -> str:
        """Sanitize a path to prevent directory traversal."""
        import os
        # Normalize the path
        normalized = os.path.normpath(path)
        # Join with base directory and normalize again
        full_path = os.path.normpath(os.path.join(base_dir, normalized))
        # Ensure it's still within base directory
        base_abs = os.path.abspath(base_dir)
        full_abs = os.path.abspath(full_path)
        if not full_abs.startswith(base_abs):
            raise ValidationError(f"Path '{path}' attempts directory traversal")
        return full_path

    @staticmethod
    def validate_terminal_command(command: str) -> bool:
        """Validate if a terminal command is safe."""
        cmd_lower = command.lower().strip()

        # Check for dangerous commands
        for dangerous in ParameterValidator.DANGEROUS_COMMANDS:
            if dangerous in cmd_lower:
                return False

        # Check for command chaining that could be dangerous
        dangerous_patterns = [
            ";", "&&", "||", "|", "`", "$", "\n", "\r"
        ]
        for pattern in dangerous_patterns:
            if pattern in command:
                # Allow pipe for safe commands like 'ls | grep'
                if pattern == "|" and not ParameterValidator._is_safe_pipe(command):
                    return False
                elif pattern != "|":
                    return False

        return True

    @staticmethod
    def _is_safe_pipe(command: str) -> bool:
        """Check if a piped command is safe."""
        parts = command.split("|")
        for part in parts:
            part = part.strip().lower()
            base_cmd = part.split()[0] if part.split() else ""
            if base_cmd and not any(
                safe in base_cmd for safe in ParameterValidator.SAFE_TERMINAL_COMMANDS
            ):
                return False
        return True


class ValidationResult:
    """Validation result object."""

    def __init__(self, valid: bool, errors: List[str] = None):
        self.valid = valid
        self.errors = errors or []

    def __bool__(self):
        return self.valid


class ToolContextBuilder:
    """Builds context with tool descriptions for LLM."""

    @staticmethod
    def build_tool_context(tools: List[Tool], include_examples: bool = True) -> str:
        """Build a comprehensive tool description context.

        Returns a formatted string describing all available tools
        that can be included in the LLM context.
        """
        context_parts = ["Available Tools:"]
        context_parts.append("=" * 50)

        for i, tool in enumerate(tools, 1):
            context_parts.append(f"\n{i}. Tool: {tool.name}")
            context_parts.append(f"   Description: {tool.description}")

            if tool.parameters:
                context_parts.append("   Parameters:")
                for param_name, param_def in tool.parameters.items():
                    param_type = param_def.get("type", "any")
                    param_desc = param_def.get("description", "")
                    required = " (required)" if param_def.get("required", True) else " (optional)"
                    context_parts.append(f"     - {param_name}: {param_type}{required}")
                    if param_desc:
                        context_parts.append(f"       {param_desc}")

            if include_examples:
                example = ToolContextBuilder._generate_example(tool)
                if example:
                    context_parts.append(f"   Example: {example}")

        context_parts.append("\n" + "=" * 50)
        context_parts.append("\nHow to use tools:")
        context_parts.append("To use a tool, respond with a JSON object in this format:")
        context_parts.append('{"action": "tool_name", "action_input": {"param1": "value1"}}')

        return "\n".join(context_parts)

    @staticmethod
    def _generate_example(tool: Tool) -> str:
        """Generate an example usage for a tool."""
        if tool.name == "python_repl":
            return '{"action": "python_repl", "action_input": {"code": "print(2+2)"}}'
        elif tool.name == "calculator":
            return '{"action": "calculator", "action_input": {"expression": "15 * 23"}}'
        elif tool.name == "search_web":
            return '{"action": "search_web", "action_input": {"query": "latest AI news"}}'
        elif tool.name == "file_reader":
            return '{"action": "file_reader", "action_input": {"path": "data.txt"}}'
        elif tool.name == "file_writer":
            return '{"action": "file_writer", "action_input": {"path": "output.txt", "content": "Hello"}}'
        elif tool.name == "terminal":
            return '{"action": "terminal", "action_input": {"command": "ls -la"}}'
        return ""

    @staticmethod
    def format_tools_for_llm(tools: List[Tool]) -> str:
        """Format tools in a simple text format for LLM context.

        This is an alternative format that's more compact.
        """
        lines = ["You have access to the following tools:"]

        for tool in tools:
            lines.append(f"\n{tool.name}: {tool.description}")
            if tool.parameters:
                params_str = ", ".join([
                    f"{k}({v.get('type', 'any')})"
                    for k, v in tool.parameters.items()
                ])
                lines.append(f"  Parameters: {params_str}")

        lines.append("\nWhen you need to use a tool, output:")
        lines.append('TOOL_CALL: {"tool": "name", "params": {...}}')

        return "\n".join(lines)


class ToolsCapabilities(ToolsInterface):
    """L5 implementation - Tools and capabilities management (no permission checks)."""

    def __init__(self, runtime: RuntimeInterface = None):
        self.runtime = runtime or RuntimeEnvironment()
        self.registry = ToolRegistry()
        self.validator = ParameterValidator()
        self.context_builder = ToolContextBuilder()

    def execute(self, action_name: str, params: Dict[str, Any],
                user_permissions: List[str] = None, timeout: int = 30) -> Observation:
        """Execute a tool (no permission checking)."""
        # Find tool
        tool = self.registry.get(action_name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{action_name}' not found")

        # Validate parameters (kept for safety)
        validation = self.validator.validate(params, tool.parameters)
        if not validation.valid:
            raise ValidationError(f"Validation failed: {'; '.join(validation.errors)}")

        # Execute
        if action_name == "python_repl":
            return self._execute_python(params, timeout)
        elif action_name == "calculator":
            return self._execute_calculator(params)
        elif action_name == "search_web":
            return self._execute_search(params)
        elif action_name == "file_reader":
            return self._execute_file_read(params)
        elif action_name == "file_writer":
            return self._execute_file_write(params)
        elif action_name == "terminal":
            return self._execute_terminal(params, timeout)
        else:
            # Check for custom handler
            if tool.handler:
                return tool.handler(params)
            raise ToolNotFoundError(f"Execution logic not implemented for '{action_name}'")

    def _execute_python(self, params: Dict, timeout: int) -> Observation:
        """Execute Python code."""
        code = params.get("code", "")

        result = self.runtime.run_code("python", code, timeout)

        # Format result
        output = result.stdout
        if result.stderr:
            output += f"\n[Error] {result.stderr}"

        # Truncate if needed
        truncated = len(output) > 10000
        if truncated:
            output = output[:9970] + "\n[Output truncated...]"

        return Observation(
            status="success" if result.exit_code == 0 else "error",
            result=output,
            execution_time=result.execution_time,
            metadata={
                "exit_code": result.exit_code,
                "truncated": truncated
            }
        )

    def _execute_calculator(self, params: Dict) -> Observation:
        """Execute calculator using safe evaluation."""
        expression = params.get("expression", "")

        # Security: validate expression contains only allowed characters
        # Allowed: digits, operators, parentheses, whitespace, and math functions
        allowed_pattern = r'^[\d\+\-\*\/\%\(\)\.\s\,]+$|^(sqrt|sin|cos|tan|log|log10|exp|pow|abs)\s*\('
        if not re.match(allowed_pattern, expression.strip(), re.IGNORECASE):
            return Observation(
                status="error",
                result="Invalid characters in expression. Only numbers, operators, and math functions allowed.",
                execution_time=0.0,
                metadata={}
            )

        try:
            # Use numexpr if available (safer and faster)
            try:
                import numexpr as ne
                result = ne.evaluate(expression).item()
            except ImportError:
                # Fallback: use eval with restricted globals/locals
                import math
                safe_dict = {
                    'sqrt': math.sqrt,
                    'sin': math.sin,
                    'cos': math.cos,
                    'tan': math.tan,
                    'pi': math.pi,
                    'e': math.e,
                    'log': math.log,
                    'log10': math.log10,
                    'exp': math.exp,
                    'pow': math.pow,
                    'abs': abs
                }
                # Compile to limit to expression only
                code = compile(expression, '<string>', 'eval')
                result = eval(code, {"__builtins__": {}}, safe_dict)

            return Observation(
                status="success",
                result=str(result),
                execution_time=0.0,
                metadata={}
            )
        except Exception as e:
            return Observation(
                status="error",
                result=str(e),
                execution_time=0.0,
                metadata={}
            )

    def _execute_search(self, params: Dict) -> Observation:
        """Execute web search."""
        # Mock implementation
        query = params.get("query", "")
        return Observation(
            status="success",
            result=f"Search results for: {query}\n[Mock results]",
            execution_time=0.5,
            metadata={}
        )

    def _execute_file_read(self, params: Dict) -> Observation:
        """Read file content."""
        import os
        path = params.get("path", "")
        encoding = params.get("encoding", "utf-8")

        try:
            # Sanitize path
            safe_path = self.validator.sanitize_path(path)

            if not os.path.exists(safe_path):
                return Observation(
                    status="error",
                    result=f"File not found: {path}",
                    execution_time=0.0,
                    metadata={}
                )

            with open(safe_path, 'r', encoding=encoding) as f:
                content = f.read()

            # Truncate if too long
            truncated = len(content) > 10000
            if truncated:
                content = content[:9970] + "\n[Content truncated...]"

            return Observation(
                status="success",
                result=content,
                execution_time=0.1,
                metadata={"truncated": truncated, "path": path}
            )
        except Exception as e:
            return Observation(
                status="error",
                result=str(e),
                execution_time=0.0,
                metadata={"path": path}
            )

    def _execute_file_write(self, params: Dict) -> Observation:
        """Write content to file."""
        import os
        path = params.get("path", "")
        content = params.get("content", "")
        encoding = params.get("encoding", "utf-8")

        try:
            # Sanitize path
            safe_path = self.validator.sanitize_path(path)

            # Create directory if needed
            dir_path = os.path.dirname(safe_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)

            with open(safe_path, 'w', encoding=encoding) as f:
                f.write(content)

            return Observation(
                status="success",
                result=f"Successfully wrote {len(content)} characters to {path}",
                execution_time=0.1,
                metadata={"path": path, "bytes_written": len(content)}
            )
        except Exception as e:
            return Observation(
                status="error",
                result=str(e),
                execution_time=0.0,
                metadata={"path": path}
            )

    def _execute_terminal(self, params: Dict, timeout: int) -> Observation:
        """Execute terminal command."""
        import subprocess
        import os
        import time

        command = params.get("command", "")
        working_dir = params.get("working_dir", ".")

        try:
            # Validate command safety
            if not self.validator.validate_terminal_command(command):
                return Observation(
                    status="error",
                    result=f"Command '{command}' is not allowed for security reasons",
                    execution_time=0.0,
                    metadata={"command": command}
                )

            # Sanitize working directory
            safe_dir = self.validator.sanitize_path(working_dir)

            start_time = time.time()
            result = subprocess.run(
                command,
                shell=True,
                cwd=safe_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            execution_time = time.time() - start_time

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr] {result.stderr}"

            # Truncate if needed
            truncated = len(output) > 10000
            if truncated:
                output = output[:9970] + "\n[Output truncated...]"

            return Observation(
                status="success" if result.returncode == 0 else "error",
                result=output,
                execution_time=execution_time,
                metadata={
                    "exit_code": result.returncode,
                    "truncated": truncated,
                    "command": command
                }
            )

        except subprocess.TimeoutExpired:
            return Observation(
                status="error",
                result=f"Command timed out after {timeout} seconds",
                execution_time=timeout,
                metadata={"command": command, "timeout": True}
            )
        except Exception as e:
            return Observation(
                status="error",
                result=str(e),
                execution_time=0.0,
                metadata={"command": command}
            )

    def get_available_tools(self, user_permissions: List[str] = None) -> List[Dict]:
        """Get list of all available tools (no permission filtering)."""
        tools = self.registry.list_tools()
        available = []

        for tool in tools:
            available.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })

        return available

    def get_tools_with_descriptions(self) -> str:
        """Get formatted tool descriptions for LLM context."""
        tools = self.registry.list_tools()
        return self.context_builder.build_tool_context(tools)

    def format_tools_for_llm(self) -> str:
        """Format tools in compact text format for LLM context."""
        tools = self.registry.list_tools()
        return self.context_builder.format_tools_for_llm(tools)

    def get_tool_descriptions_openai_format(self) -> List[Dict]:
        """Get tool descriptions in OpenAI function calling format."""
        tools = self.registry.list_tools()
        result = []
        for tool in tools:
            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": [
                            k for k, v in tool.parameters.items()
                            if v.get("required", True)
                        ]
                    }
                }
            })
        return result

    def register_tool(self, name: str, tool: Tool) -> None:
        """Register a new tool dynamically."""
        self.registry.register(name, tool)

    def unregister_tool(self, name: str) -> None:
        """Unregister a tool."""
        self.registry.unregister(name)
