"""Shared data models for all layers."""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


class StandardEvent(BaseModel):
    """L1 output / L2 input - Standardized event from any channel."""
    channel: str = Field(..., description="Channel source: telegram, websocket, webhook")
    user_id: str = Field(..., description="Unique user identifier")
    content: str = Field(..., description="User input content")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionContext(BaseModel):
    """L2 output / L3 input - Stateful session context."""
    session_id: str = Field(..., description="Session UUID")
    user_id: str = Field(..., description="User ID")
    current_query: str = Field(..., description="Current user query")
    history: List[Dict[str, str]] = Field(default_factory=list, description="Conversation history (OpenAI format)")
    user_permissions: List[str] = Field(default_factory=list, description="User permissions")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentAction(BaseModel):
    """L3 output (internal) - Tool call instruction."""
    action: str = Field(..., description="Tool name")
    action_input: Dict[str, Any] = Field(..., description="Tool parameters")
    thought: Optional[str] = Field(None, description="Reasoning process")


class Observation(BaseModel):
    """L5 output / L3 input - Tool execution result."""
    status: str = Field(..., description="success or error")
    result: str = Field(..., description="Execution result (max 10000 chars)")
    execution_time: float = Field(..., description="Execution time in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """L6 output / L5 input - Code execution result."""
    exit_code: int = Field(..., description="0 = success, non-zero = error")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    execution_time: float = Field(..., description="Execution time in seconds")
    resource_usage: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """L4 data structure - Document for vector storage."""
    id: str = Field(..., description="Document ID")
    content: str = Field(..., description="Document content")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")
