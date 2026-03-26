"""L5: Tools & Capabilities Layer - Tool routing and security."""
from typing import List, Dict, Any
from src.models import Observation
from src.interfaces import ToolsInterface, RuntimeInterface
from src.l6_runtime import RuntimeEnvironment


class ToolNotFoundError(Exception):
    """Raised when tool is not found."""
    pass


class ValidationError(Exception):
    """Raised when parameter validation fails."""
    pass


class PermissionDeniedError(Exception):
    """Raised when user lacks permission."""
    pass


class ExecutionTimeoutError(Exception):
    """Raised when execution times out."""
    pass


class Tool:
    """Tool definition."""
    
    def __init__(self, name: str, description: str, 
                 parameters: Dict, required_permission: str):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required_permission = required_permission


class ToolsCapabilities(ToolsInterface):
    """L5 implementation - Tools and capabilities management."""
    
    TOOL_DEFINITIONS = {
        "python_repl": Tool(
            name="python_repl",
            description="Execute Python code",
            parameters={
                "code": {"type": "string", "description": "Python code to execute"}
            },
            required_permission="execute_code"
        ),
        "calculator": Tool(
            name="calculator",
            description="Perform mathematical calculations",
            parameters={
                "expression": {"type": "string", "description": "Math expression"}
            },
            required_permission="none"
        ),
        "search_web": Tool(
            name="search_web",
            description="Search the web",
            parameters={
                "query": {"type": "string", "description": "Search query"}
            },
            required_permission="web_access"
        )
    }
    
    def __init__(self, runtime: RuntimeInterface = None):
        self.runtime = runtime or RuntimeEnvironment()
    
    def execute(self, action_name: str, params: Dict[str, Any],
                user_permissions: List[str], timeout: int = 30) -> Observation:
        """Execute a tool."""
        # Find tool
        tool = self.TOOL_DEFINITIONS.get(action_name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{action_name}' not found")
        
        # Check permission
        if tool.required_permission != "none":
            if tool.required_permission not in user_permissions and "admin" not in user_permissions:
                raise PermissionDeniedError(
                    f"Permission '{tool.required_permission}' required for tool '{action_name}'"
                )
        
        # Validate parameters
        self._validate_params(params, tool.parameters)
        
        # Execute
        if action_name == "python_repl":
            return self._execute_python(params, timeout)
        elif action_name == "calculator":
            return self._execute_calculator(params)
        elif action_name == "search_web":
            return self._execute_search(params)
        else:
            raise ToolNotFoundError(f"Execution logic not implemented for '{action_name}'")
    
    def _validate_params(self, params: Dict, schema: Dict):
        """Validate parameters against schema."""
        for param_name, param_def in schema.items():
            if param_name not in params:
                raise ValidationError(f"Missing required parameter: {param_name}")
    
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
        """Execute calculator."""
        expression = params.get("expression", "")
        try:
            # Safe evaluation (simple math only)
            result = eval(expression, {"__builtins__": {}}, {})
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
    
    def get_available_tools(self, user_permissions: List[str]) -> List[Dict]:
        """Get list of available tools for user."""
        available = []
        
        for tool in self.TOOL_DEFINITIONS.values():
            # Check permission
            if tool.required_permission == "none" or \
               tool.required_permission in user_permissions or \
               "admin" in user_permissions:
                available.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters
                    }
                })
        
        return available
