"""L3: Orchestration Layer - Task planning, ReAct loop, LLM management."""
import os
import json
import time
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Iterator
from abc import ABC, abstractmethod
from src.models import SessionContext, AgentAction, Observation
from src.interfaces import MemoryInterface, ToolsInterface
from src.l4_memory import MemoryKnowledge
from src.l5_tools import ToolsCapabilities


from src.exceptions import (
    LLMError, MaxIterationsExceeded, ToolExecutionError
)

# Re-export for backward compatibility
__all__ = ['LLMError', 'MaxIterationsExceeded', 'ToolExecutionError']


class ProviderType(str, Enum):
    """Enum for LLM provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CLAUDE = "claude"  # Alias for anthropic
    KIMI = "kimi"
    MOONSHOT = "moonshot"  # Alias for kimi
    MOCK = "mock"


# Constants for fallback plan
FALLBACK_PLAN_STEP = 1
FALLBACK_PLAN_ACTION = "llm"
FALLBACK_PLAN_DESCRIPTION = "Process user request directly"


def create_fallback_plan(query: str) -> List[Dict]:
    """Create a fallback plan when task planning fails."""
    return [{
        "step": FALLBACK_PLAN_STEP,
        "action": FALLBACK_PLAN_ACTION,
        "description": FALLBACK_PLAN_DESCRIPTION,
        "input": {"query": query},
        "depends_on": []
    }]


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Call LLM for completion."""
        pass

    @abstractmethod
    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Stream LLM response."""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """Base class for OpenAI-compatible API providers (OpenAI, Kimi, etc.)."""

    def __init__(self, api_key: str, model: str, base_url: str = None,
                 provider_name: str = "OpenAI"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.provider_name = provider_name
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                raise LLMError(f"OpenAI package not installed. Run: pip install openai")
        return self._client

    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Call API for completion."""
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                **kwargs
            )

            message = response.choices[0].message

            # Check if there's a tool call
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                return AgentAction(
                    action=tool_call.function.name,
                    action_input=json.loads(tool_call.function.arguments),
                    thought=message.content or "Using tool to complete the task"
                )

            return message.content

        except Exception as e:
            raise LLMError(f"{self.provider_name} API error: {str(e)}")

    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Stream LLM response."""
        try:
            client = self._get_client()
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **kwargs
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise LLMError(f"{self.provider_name} streaming error: {str(e)}")


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI GPT provider."""

    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        super().__init__(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            model=model,
            provider_name="OpenAI"
        )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str = None, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise LLMError("Anthropic package not installed. Run: pip install anthropic")
        return self._client

    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Call Anthropic API for completion."""
        try:
            client = self._get_client()

            # Convert OpenAI format to Anthropic format
            system_msg = ""
            anthropic_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_msg += msg["content"] + "\n"
                else:
                    anthropic_messages.append(msg)

            # Convert tools format if provided
            anthropic_tools = None
            if tools:
                anthropic_tools = []
                for tool in tools:
                    anthropic_tools.append({
                        "name": tool["function"]["name"],
                        "description": tool["function"]["description"],
                        "input_schema": tool["function"]["parameters"]
                    })

            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_msg.strip() if system_msg else None,
                messages=anthropic_messages,
                tools=anthropic_tools,
                **kwargs
            )

            # Check for tool use
            for content in response.content:
                if content.type == "tool_use":
                    return AgentAction(
                        action=content.name,
                        action_input=content.input,
                        thought="Using tool to complete the task"
                    )

            # Return text response
            text_content = " ".join([c.text for c in response.content if c.type == "text"])
            return text_content

        except Exception as e:
            raise LLMError(f"Anthropic API error: {str(e)}")

    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Stream LLM response from Anthropic."""
        try:
            client = self._get_client()

            # Convert OpenAI format to Anthropic format
            system_msg = ""
            anthropic_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_msg += msg["content"] + "\n"
                else:
                    anthropic_messages.append(msg)

            with client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=system_msg.strip() if system_msg else None,
                messages=anthropic_messages,
                **kwargs
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            raise LLMError(f"Anthropic streaming error: {str(e)}")


class KimiProvider(OpenAICompatibleProvider):
    """Moonshot Kimi provider."""

    def __init__(self, api_key: str = None, model: str = "moonshot-v1-128k"):
        super().__init__(
            api_key=api_key or os.getenv("KIMI_API_KEY"),
            model=model,
            base_url="https://api.moonshot.cn/v1",
            provider_name="Kimi"
        )


class MockProvider(LLMProvider):
    """Mock provider for testing."""

    def __init__(self, model: str = "mock"):
        self.model = model

    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Mock completion - simple keyword matching."""
        last_message = messages[-1]["content"] if messages else ""

        # Check for calculator patterns
        if "calculate" in last_message.lower() or "1+1" in last_message or "=" in last_message:
            # Extract math expression if present
            return AgentAction(
                action="calculator",
                action_input={"expression": "1+1"},
                thought="I need to calculate this"
            )

        # Check for code patterns
        if "code" in last_message.lower() or "python" in last_message.lower():
            return AgentAction(
                action="python_repl",
                action_input={"code": "print('Hello, World!')"},
                thought="I need to execute Python code"
            )

        return f"I received your message: {last_message}"

    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Mock streaming - yield words."""
        response = self.complete(messages)
        if isinstance(response, AgentAction):
            response = f"Using tool: {response.action}"
        # Yield word by word
        for word in response.split():
            yield word + " "


class LLMManager:
    """LLM manager supporting multiple providers with retry and streaming."""

    PROVIDERS = {
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.CLAUDE: AnthropicProvider,  # Alias
        ProviderType.KIMI: KimiProvider,
        ProviderType.MOONSHOT: KimiProvider,  # Alias
        ProviderType.MOCK: MockProvider
    }

    def __init__(self, provider: Union[str, ProviderType] = ProviderType.MOCK,
                 model: str = None, api_key: str = None,
                 max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize LLM manager.

        Args:
            provider: Provider name or ProviderType enum
            model: Model name (optional, uses provider default if not set)
            api_key: API key (optional, reads from env if not set)
            max_retries: Maximum number of retries on failure
            retry_delay: Initial delay between retries (doubles each retry)
        """
        # Convert string to enum if needed
        if isinstance(provider, str):
            try:
                self.provider_name = ProviderType(provider.lower())
            except ValueError:
                raise LLMError(f"Unknown provider: {provider}. Available: {[p.value for p in ProviderType]}")
        else:
            self.provider_name = provider

        if self.provider_name not in self.PROVIDERS:
            raise LLMError(f"Unknown provider: {provider}")

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        provider_class = self.PROVIDERS[self.provider_name]
        self.provider = provider_class(api_key=api_key, model=model) if model or api_key else provider_class()

    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Call LLM for completion with retry logic."""
        last_error = None
        delay = self.retry_delay
        max_delay = 60  # Cap at 60 seconds

        for attempt in range(self.max_retries):
            try:
                return self.provider.complete(messages, tools, **kwargs)
            except LLMError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Add jitter (±25%) and cap delay
                    import random
                    jittered_delay = delay * (0.75 + random.random() * 0.5)
                    time.sleep(min(jittered_delay, max_delay))
                    delay *= 2  # Exponential backoff
                continue

        raise LLMError(f"Failed after {self.max_retries} attempts: {str(last_error)}")

    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Stream LLM response with retry logic."""
        last_error = None
        delay = self.retry_delay
        max_delay = 60

        for attempt in range(self.max_retries):
            try:
                yield from self.provider.stream(messages, **kwargs)
                return
            except LLMError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    import random
                    jittered_delay = delay * (0.75 + random.random() * 0.5)
                    time.sleep(min(jittered_delay, max_delay))
                    delay *= 2
                continue

        raise LLMError(f"Streaming failed after {self.max_retries} attempts: {str(last_error)}")

    def switch_provider(self, provider: Union[str, ProviderType], model: str = None, api_key: str = None):
        """Switch to a different provider."""
        if isinstance(provider, str):
            try:
                self.provider_name = ProviderType(provider.lower())
            except ValueError:
                raise LLMError(f"Unknown provider: {provider}")
        else:
            self.provider_name = provider

        if self.provider_name not in self.PROVIDERS:
            raise LLMError(f"Unknown provider: {provider}")

        provider_class = self.PROVIDERS[self.provider_name]
        self.provider = provider_class(api_key=api_key, model=model) if model or api_key else provider_class()


class TaskPlanner:
    """Task planner using a small model for planning."""

    def __init__(self, llm_manager: LLMManager = None):
        self.llm_manager = llm_manager or LLMManager(provider="mock")
        # Use a lighter/smaller model for planning if available
        self.planning_llm = LLMManager(provider="mock")  # Can be configured separately

    def create_plan(self, query: str, context: str = "", available_tools: List[Dict] = None) -> List[Dict]:
        """Create a task plan for the given query.

        Returns a list of steps, each with:
        - step: step number
        - action: tool name or "llm"
        - description: what this step does
        - depends_on: list of step numbers this depends on
        """
        tools_desc = ""
        if available_tools:
            tools_desc = "\nAvailable tools:\n" + json.dumps(available_tools, indent=2)

        planning_prompt = f"""You are a task planner. Break down the following user request into a sequence of steps.
Each step should use either a tool or LLM reasoning.

User request: {query}
Context: {context}{tools_desc}

Output a JSON array of steps with this format:
[
    {{
        "step": 1,
        "action": "tool_name or 'llm'",
        "description": "what this step does",
        "input": {{"key": "value"}},
        "depends_on": []
    }}
]

Rules:
- Use tools when specific capabilities are needed (calculator, web search, code execution)
- Use 'llm' for reasoning, summarization, or when no tool fits
- Number steps sequentially
- Use depends_on to indicate dependencies between steps

Output only valid JSON:"""

        messages = [
            {"role": "system", "content": "You are a helpful task planning assistant."},
            {"role": "user", "content": planning_prompt}
        ]

        try:
            response = self.planning_llm.complete(messages, temperature=0.2)
            if isinstance(response, AgentAction):
                response = response.action_input.get("code", "[]")

            # Parse the plan
            if isinstance(response, str):
                # Try to extract JSON from the response
                try:
                    # Find JSON array in the response
                    start = response.find("[")
                    end = response.rfind("]") + 1
                    if start >= 0 and end > start:
                        plan = json.loads(response[start:end])
                    else:
                        plan = json.loads(response)
                except (json.JSONDecodeError, ValueError):
                    # Fallback: simple single-step plan
                    return create_fallback_plan(query)
            else:
                plan = response if isinstance(response, list) else []

            # Ensure plan is not empty
            if not plan:
                return create_fallback_plan(query)

            return plan

        except Exception as e:
            # Fallback to simple plan
            return create_fallback_plan(query)

    def get_next_step(self, plan: List[Dict], completed_steps: List[int]) -> Optional[Dict]:
        """Get the next executable step from the plan."""
        for step in plan:
            step_num = step.get("step")
            if step_num in completed_steps:
                continue

            # Check if dependencies are satisfied
            depends_on = step.get("depends_on", [])
            if all(dep in completed_steps for dep in depends_on):
                return step

        return None


class MemoryAccessor:
    """Memory accessor for retrieving relevant context."""

    def __init__(self, memory: MemoryInterface = None):
        self.memory = memory or MemoryKnowledge()

    def retrieve_for_query(self, query: str, session_id: str,
                          top_k: int = 3, include_history: bool = True) -> Dict[str, Any]:
        """Retrieve relevant information for a query.

        Returns:
            Dictionary with:
            - knowledge: list of relevant knowledge snippets
            - history_summary: summary of recent conversation
            - related_queries: similar past queries
        """
        result = {
            "knowledge": [],
            "history_summary": "",
            "related_queries": []
        }

        # Search knowledge base
        try:
            knowledge = self.memory.search(query, top_k=top_k)
            result["knowledge"] = knowledge
        except Exception:
            pass

        # Retrieve conversation history
        if include_history:
            try:
                history = self.memory.retrieve_history(session_id, limit=10)
                if history:
                    # Summarize history
                    user_msgs = [h["content"] for h in history if h.get("role") == "user"]
                    result["related_queries"] = user_msgs[-3:] if len(user_msgs) > 0 else []
                    result["history_summary"] = f"Recent conversation has {len(history)} messages"
            except Exception:
                pass

        return result

    def format_context(self, retrieval_result: Dict[str, Any]) -> str:
        """Format retrieved context for LLM consumption."""
        context_parts = []

        if retrieval_result.get("knowledge"):
            context_parts.append("Relevant knowledge:")
            for i, item in enumerate(retrieval_result["knowledge"], 1):
                context_parts.append(f"  [{i}] {item}")

        if retrieval_result.get("history_summary"):
            context_parts.append(f"\nConversation: {retrieval_result['history_summary']}")

        if retrieval_result.get("related_queries"):
            context_parts.append("Related previous queries:")
            for q in retrieval_result["related_queries"]:
                context_parts.append(f"  - {q}")

        return "\n".join(context_parts) if context_parts else ""


class Orchestration:
    """L3 implementation - Orchestration and ReAct loop."""

    MAX_ITERATIONS = 5

    def __init__(self, memory: MemoryInterface = None,
                 tools: ToolsInterface = None,
                 llm_manager: LLMManager = None):
        self.memory = memory or MemoryKnowledge()
        self.tools = tools or ToolsCapabilities()
        self.llm_manager = llm_manager or LLMManager()
        self.task_planner = TaskPlanner(self.llm_manager)
        self.memory_accessor = MemoryAccessor(self.memory)
        self.iteration_count = 0
        self.current_plan: List[Dict] = []
        self.completed_steps: List[int] = []

    def run(self, context: SessionContext,
            observation: Observation = None) -> Union[str, AgentAction]:
        """Run orchestration logic with task planning."""
        # Check max iterations
        if self.iteration_count >= self.MAX_ITERATIONS:
            raise MaxIterationsExceeded("Maximum iterations reached")

        # Retrieve relevant context using MemoryAccessor
        retrieval_result = self.memory_accessor.retrieve_for_query(
            context.current_query,
            context.session_id
        )
        knowledge_context = self.memory_accessor.format_context(retrieval_result)

        # Get available tools with descriptions for planning
        available_tools = self.tools.get_available_tools([])

        # Create task plan if not exists (first run)
        if not self.current_plan and not observation:
            self.current_plan = self.task_planner.create_plan(
                context.current_query,
                knowledge_context,
                available_tools
            )

        # Get next step from plan
        if self.current_plan:
            next_step = self.task_planner.get_next_step(self.current_plan, self.completed_steps)

            if next_step:
                step_action = next_step.get("action", "llm")
                step_input = next_step.get("input", {})

                # Mark step as completed
                self.completed_steps.append(next_step.get("step"))

                # If action is a tool, return AgentAction
                if step_action != "llm" and step_action in [t.get("name") for t in available_tools]:
                    self.iteration_count += 1
                    return AgentAction(
                        action=step_action,
                        action_input=step_input,
                        thought=f"Step {next_step.get('step')}: {next_step.get('description', '')}"
                    )

        # Build messages for LLM
        messages = self._build_messages(context, observation, retrieval_result["knowledge"])

        # Call LLM with tools available
        response = self.llm_manager.complete(messages, available_tools)

        # If it's an AgentAction, increment counter and return it
        if isinstance(response, AgentAction):
            self.iteration_count += 1
            return response

        # Otherwise it's a final response
        return response

    def run_streaming(self, context: SessionContext) -> Iterator[str]:
        """Run orchestration with streaming response.

        This is used for chat interfaces where you want to show
        the response as it's being generated.
        """
        # Retrieve context
        retrieval_result = self.memory_accessor.retrieve_for_query(
            context.current_query,
            context.session_id
        )

        # Build messages
        messages = self._build_messages(context, None, retrieval_result["knowledge"])

        # Stream response
        yield from self.llm_manager.stream(messages)

    def _build_messages(self, context: SessionContext,
                       observation: Observation = None,
                       knowledge: List[str] = None) -> List[Dict]:
        """Build messages for LLM."""
        messages = []

        # Add system prompt
        messages.append({
            "role": "system",
            "content": "You are a helpful AI assistant with access to tools. Use tools when appropriate."
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

    def reset_plan(self):
        """Reset the current task plan."""
        self.current_plan = []
        self.completed_steps = []
        self.iteration_count = 0
