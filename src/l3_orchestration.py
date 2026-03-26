"""L3: Orchestration Layer - Intent recognition, task planning, ReAct loop."""
from typing import List, Dict, Any, Optional, Union
from src.models import SessionContext, AgentAction, Observation
from src.interfaces import MemoryInterface, ToolsInterface
from src.l4_memory import MemoryKnowledge
from src.l5_tools import ToolsCapabilities


class LLMError(Exception):
    """Raised when LLM call fails."""
    pass


class MaxIterationsExceeded(Exception):
    """Raised when max ReAct iterations reached."""
    pass


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass


class IntentRecognizer:
    """Simple intent recognizer."""
    
    INTENT_KEYWORDS = {
        "chat": ["hello", "hi", "hey", "how are you", "good morning", "good evening"],
        "query": ["what", "when", "where", "who", "why", "how", "?"],
        "code": ["code", "python", "javascript", "function", "program", "write"],
        "action": ["calculate", "compute", "search", "find", "look up", "execute", "calculate this", "search for"]
    }
    
    def recognize(self, query: str, history: List[Dict]) -> str:
        """Recognize intent from query."""
        query_lower = query.lower()
        import re
        
        # Check for chat first (greetings)
        for keyword in self.INTENT_KEYWORDS["chat"]:
            # Use word boundary for short keywords
            if len(keyword) <= 3:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, query_lower):
                    return "chat"
            elif keyword in query_lower:
                return "chat"
        
        # Check for action keywords
        for keyword in self.INTENT_KEYWORDS["action"]:
            if keyword in query_lower:
                return "action"
        
        for keyword in self.INTENT_KEYWORDS["code"]:
            if keyword in query_lower:
                return "code"
        
        for keyword in self.INTENT_KEYWORDS["query"]:
            if keyword in query_lower:
                return "query"
        
        return "chat"  # Default to chat


class LLMManager:
    """Simple LLM manager (mock)."""
    
    def complete(self, messages: List[Dict], tools: List[Dict] = None) -> Union[str, AgentAction]:
        """Call LLM for completion."""
        # Mock implementation
        last_message = messages[-1]["content"] if messages else ""
        
        if "calculate" in last_message.lower() or "1+1" in last_message:
            return AgentAction(
                action="python_repl",
                action_input={"code": "print(1+1)"},
                thought="I need to calculate this"
            )
        
        return f"I received your message: {last_message}"
    
    def stream(self, messages: List[Dict]):
        """Stream LLM response."""
        yield "Response text..."


class Orchestration:
    """L3 implementation - Orchestration and ReAct loop."""
    
    MAX_ITERATIONS = 5
    
    def __init__(self, memory: MemoryInterface = None, 
                 tools: ToolsInterface = None):
        self.memory = memory or MemoryKnowledge()
        self.tools = tools or ToolsCapabilities()
        self.intent_recognizer = IntentRecognizer()
        self.llm_manager = LLMManager()
        self.iteration_count = 0
    
    def run(self, context: SessionContext, 
            observation: Observation = None) -> Union[str, AgentAction]:
        """Run orchestration logic."""
        # Check max iterations
        if self.iteration_count >= self.MAX_ITERATIONS:
            raise MaxIterationsExceeded("Maximum iterations reached")
        
        # Retrieve relevant knowledge
        relevant_knowledge = self.memory.search(context.current_query, top_k=3)
        
        # Recognize intent
        intent = self.intent_recognizer.recognize(
            context.current_query, 
            context.history
        )
        
        # Build messages for LLM
        messages = self._build_messages(context, observation, relevant_knowledge)
        
        # Get available tools
        available_tools = self.tools.get_available_tools(context.user_permissions)
        
        # Call LLM
        response = self.llm_manager.complete(messages, available_tools)
        
        # If it's an AgentAction, increment counter and return it
        if isinstance(response, AgentAction):
            self.iteration_count += 1
            return response
        
        # Otherwise it's a final response
        return response
    
    def _build_messages(self, context: SessionContext, 
                       observation: Observation = None,
                       knowledge: List[str] = None) -> List[Dict]:
        """Build messages for LLM."""
        messages = []
        
        # Add system prompt
        messages.append({
            "role": "system",
            "content": "You are a helpful AI assistant."
        })
        
        # Add knowledge if available
        if knowledge:
            messages.append({
                "role": "system",
                "content": f"Relevant knowledge: {' '.join(knowledge)}"
            })
        
        # Add history
        for msg in context.history[-5:]:  # Last 5 messages
            messages.append(msg)
        
        # Add current query
        messages.append({
            "role": "user",
            "content": context.current_query
        })
        
        # Add observation if available
        if observation:
            messages.append({
                "role": "system",
                "content": f"Tool result: {observation.result}"
            })
        
        return messages
    
    def format_response(self, content: str, include_thoughts: bool = False) -> str:
        """Format response for output."""
        if include_thoughts:
            return f"[Thought Process]\n{content}"
        return content
