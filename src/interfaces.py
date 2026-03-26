"""Interface definitions for dependency injection."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.models import (
    SessionContext, Observation, ExecutionResult, 
    Document, AgentAction
)


class MemoryInterface(ABC):
    """L4 interface - Memory and knowledge layer."""
    
    @abstractmethod
    def search(self, query: str, top_k: int = 5, 
               filters: Optional[Dict] = None) -> List[str]:
        """Search for relevant documents."""
        pass
    
    @abstractmethod
    def store(self, document: str, metadata: Dict[str, Any]) -> bool:
        """Store a document."""
        pass
    
    @abstractmethod
    def store_conversation(self, session_id: str, 
                          messages: List[Dict[str, str]]) -> bool:
        """Store conversation history."""
        pass
    
    @abstractmethod
    def retrieve_history(self, session_id: str, 
                        limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve conversation history."""
        pass


class ToolsInterface(ABC):
    """L5 interface - Tools and capabilities layer."""
    
    @abstractmethod
    def execute(self, action_name: str, params: Dict[str, Any],
                user_permissions: List[str], timeout: int = 30) -> Observation:
        """Execute a tool."""
        pass
    
    @abstractmethod
    def get_available_tools(self, user_permissions: List[str]) -> List[Dict]:
        """Get list of available tools for LLM."""
        pass


class RuntimeInterface(ABC):
    """L6 interface - Runtime and environment layer."""
    
    @abstractmethod
    def run_code(self, language: str, code: str, 
                 timeout: int = 30,
                 environment_config: Optional[Dict] = None) -> ExecutionResult:
        """Execute code in sandbox."""
        pass
