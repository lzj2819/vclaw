"""Debug tests for L3 Orchestration with detailed logging."""
import pytest
import logging
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l3_orchestration import Orchestration, LLMManager, MemoryAccessor, TaskPlanner
from src.models import SessionContext, AgentAction, Observation

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DebugOrchestration(Orchestration):
    """Orchestration with detailed logging of intermediate variables."""

    def run(self, context, observation=None):
        """Run with detailed logging."""
        logger.info("=" * 60)
        logger.info("L3 Orchestration RUN START")
        logger.info("=" * 60)

        # Log input context
        logger.debug(f"Input SessionContext:")
        logger.debug(f"  - session_id: {context.session_id}")
        logger.debug(f"  - user_id: {context.user_id}")
        logger.debug(f"  - current_query: {context.current_query}")
        logger.debug(f"  - history length: {len(context.history)}")
        logger.debug(f"  - user_permissions: {context.user_permissions}")

        # Log observation if present
        if observation:
            logger.debug(f"Input Observation:")
            logger.debug(f"  - status: {observation.status}")
            logger.debug(f"  - result: {observation.result}")
            logger.debug(f"  - execution_time: {observation.execution_time}")
        else:
            logger.debug("Input Observation: None")

        # Check max iterations
        logger.debug(f"Current iteration_count: {self.iteration_count}")
        if self.iteration_count >= self.MAX_ITERATIONS:
            logger.error(f"Max iterations ({self.MAX_ITERATIONS}) exceeded!")
            raise Exception("Maximum iterations reached")

        # Use MemoryAccessor for context retrieval
        logger.info("-" * 40)
        logger.info("STEP 1: Context Retrieval via MemoryAccessor")
        retrieval_result = self.memory_accessor.retrieve_for_query(
            context.current_query,
            context.session_id
        )
        knowledge_context = self.memory_accessor.format_context(retrieval_result)
        logger.debug(f"Retrieved {len(retrieval_result.get('knowledge', []))} knowledge items")
        logger.debug(f"Context preview: {knowledge_context[:200]}...")

        # Get available tools
        logger.info("-" * 40)
        logger.info("STEP 2: Get Available Tools")
        available_tools = self.tools.get_available_tools(context.user_permissions)
        logger.debug(f"Available tools for permissions {context.user_permissions}:")
        for tool in available_tools:
            logger.debug(f"  - {tool.get('function', {}).get('name', 'unknown')}: {tool.get('function', {}).get('description', 'N/A')[:50]}")

        # Create task plan if first run
        if not self.current_plan and not observation:
            logger.info("-" * 40)
            logger.info("STEP 3: Task Planning")
            self.current_plan = self.task_planner.create_plan(
                context.current_query,
                knowledge_context,
                available_tools
            )
            logger.debug(f"Created plan with {len(self.current_plan)} steps")
            for step in self.current_plan:
                logger.debug(f"  Step {step.get('step')}: {step.get('action')} - {step.get('description')}")

        # Get next step from plan
        if self.current_plan:
            logger.info("-" * 40)
            logger.info("STEP 4: Get Next Step from Plan")
            next_step = self.task_planner.get_next_step(self.current_plan, self.completed_steps)

            if next_step:
                step_action = next_step.get("action", "llm")
                step_input = next_step.get("input", {})
                logger.debug(f"Next step: {next_step.get('step')} - {step_action}")

                # Mark step as completed
                self.completed_steps.append(next_step.get("step"))

                # If action is a tool, return AgentAction
                if step_action != "llm" and step_action in [t.get("function", {}).get("name") for t in available_tools]:
                    self.iteration_count += 1
                    logger.info(f"Returning AgentAction for tool: {step_action}")
                    return AgentAction(
                        action=step_action,
                        action_input=step_input,
                        thought=f"Step {next_step.get('step')}: {next_step.get('description', '')}"
                    )

        # Build messages for LLM
        logger.info("-" * 40)
        logger.info("STEP 5: Build Messages for LLM")
        messages = self._build_messages(context, observation, retrieval_result.get("knowledge", []))
        logger.debug(f"Built {len(messages)} messages:")
        for i, msg in enumerate(messages):
            content_preview = msg.get('content', '')[:100]
            if len(msg.get('content', '')) > 100:
                content_preview += "..."
            logger.debug(f"  [{i}] role={msg.get('role')}, content={content_preview}")

        # Call LLM
        logger.info("-" * 40)
        logger.info("STEP 6: LLM Call")
        logger.debug(f"Calling LLM with {len(messages)} messages and {len(available_tools)} tools")
        response = self.llm_manager.complete(messages, available_tools)

        # Log response
        if isinstance(response, AgentAction):
            logger.info(f"LLM returned AgentAction:")
            logger.debug(f"  - action: {response.action}")
            logger.debug(f"  - action_input: {response.action_input}")
            logger.debug(f"  - thought: {response.thought}")
            self.iteration_count += 1
            logger.debug(f"Iteration count incremented to: {self.iteration_count}")
        else:
            logger.info(f"LLM returned final response (string):")
            logger.debug(f"  - response: {response[:200]}{'...' if len(response) > 200 else ''}")

        logger.info("=" * 60)
        logger.info("L3 Orchestration RUN END")
        logger.info("=" * 60)

        return response


class TestOrchestrationDebug:
    """Debug tests for L3 Orchestration with detailed logging."""

    def test_simple_chat_response_debug(self):
        """TC-L3-001-DEBUG: Simple chat response (with detailed logging)"""
        logger.info("\n\n>>> TEST: Simple Chat Response <<<")

        orchestration = DebugOrchestration()
        context = SessionContext(
            session_id="test_debug_001",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        logger.info(f"\n>>> FINAL RESULT TYPE: {type(result).__name__}")
        logger.info(f">>> FINAL RESULT: {result}")

        assert isinstance(result, str)
        assert "Hello" in result or "message" in result

    def test_single_tool_call_debug(self):
        """TC-L3-002-DEBUG: Single tool call (with detailed logging)"""
        logger.info("\n\n>>> TEST: Single Tool Call <<<")

        orchestration = DebugOrchestration()
        context = SessionContext(
            session_id="test_debug_002",
            user_id="user_123",
            current_query="Calculate 1+1",
            history=[],
            user_permissions=["admin"]
        )

        # First call - should return AgentAction
        logger.info("\n>>> FIRST CALL (expecting AgentAction)")
        result = orchestration.run(context)

        logger.info(f"\n>>> FIRST RESULT TYPE: {type(result).__name__}")
        if isinstance(result, AgentAction):
            logger.info(f">>> AgentAction.action: {result.action}")
            logger.info(f">>> AgentAction.action_input: {result.action_input}")
            logger.info(f">>> AgentAction.thought: {result.thought}")

        assert isinstance(result, AgentAction)
        assert result.action == "calculator"

        # Second call - with observation, should return final response
        logger.info("\n>>> SECOND CALL (with observation, expecting final response)")
        observation = Observation(
            status="success",
            result="2",
            execution_time=0.1,
            metadata={}
        )
        result = orchestration.run(context, observation)

        logger.info(f"\n>>> SECOND RESULT TYPE: {type(result).__name__}")
        logger.info(f">>> SECOND RESULT: {result}")

        assert isinstance(result, str)

    def test_memory_accessor_debug(self):
        """TC-L3-006-DEBUG: MemoryAccessor retrieval (with detailed logging)"""
        logger.info("\n\n>>> TEST: MemoryAccessor <<<")

        orchestration = DebugOrchestration()
        context = SessionContext(
            session_id="test_debug_003",
            user_id="user_123",
            current_query="Tell me about Python",
            history=[],
            user_permissions=["user"]
        )

        # Direct memory access via MemoryAccessor
        logger.info("\n>>> Direct MemoryAccessor.retrieve_for_query() call")
        result = orchestration.memory_accessor.retrieve_for_query(
            context.current_query,
            context.session_id
        )
        logger.info(f">>> MemoryAccessor returned:")
        logger.info(f"    knowledge items: {len(result.get('knowledge', []))}")
        logger.info(f"    history_summary: {result.get('history_summary', '')}")
        logger.info(f"    related_queries: {result.get('related_queries', [])}")

        # Full orchestration run
        logger.info("\n>>> Full orchestration run")
        result = orchestration.run(context)
        logger.info(f"\n>>> FINAL RESULT: {result}")

    def test_message_building_debug(self):
        """DEBUG: Detailed test of message building process"""
        logger.info("\n\n>>> TEST: Message Building <<<")

        orchestration = DebugOrchestration()

        # Test with history and knowledge
        context = SessionContext(
            session_id="test_debug_004",
            user_id="user_456",
            current_query="What is AI?",
            history=[
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": "Previous answer"}
            ],
            user_permissions=["user"]
        )

        # Mock memory to return knowledge
        with patch.object(orchestration.memory, 'search') as mock_search:
            mock_search.return_value = [
                "AI stands for Artificial Intelligence",
                "AI involves machine learning and deep learning"
            ]

            # Build messages with knowledge
            knowledge = orchestration.memory.search(context.current_query, top_k=3)
            messages = orchestration._build_messages(context, None, knowledge)

            logger.info(f"\n>>> Built {len(messages)} messages:")
            for i, msg in enumerate(messages):
                content = msg.get('content', '')
                logger.info(f"\n  Message [{i}]:")
                logger.info(f"    role: {msg.get('role')}")
                logger.info(f"    content: {content[:150]}{'...' if len(content) > 150 else ''}")

            # Verify message structure
            assert messages[0]['role'] == 'system'
            assert messages[0]['content'] == 'You are a helpful AI assistant with access to tools. Use tools when appropriate.'

    def test_iteration_count_debug(self):
        """DEBUG: Test iteration count and max iteration limit"""
        logger.info("\n\n>>> TEST: Iteration Count <<<")

        orchestration = DebugOrchestration()
        context = SessionContext(
            session_id="test_debug_005",
            user_id="user_123",
            current_query="Calculate 1+1",
            history=[],
            user_permissions=["admin"]
        )

        logger.info(f"Initial iteration_count: {orchestration.iteration_count}")
        logger.info(f"MAX_ITERATIONS: {orchestration.MAX_ITERATIONS}")

        # Multiple calls to increment counter
        for i in range(3):
            logger.info(f"\n>>> Call #{i+1}")
            result = orchestration.run(context)
            logger.info(f"iteration_count after call: {orchestration.iteration_count}")

        logger.info(f"\n>>> Final iteration_count: {orchestration.iteration_count}")
        assert orchestration.iteration_count == 3

    def test_task_planner_debug(self):
        """DEBUG: Test TaskPlanner functionality"""
        logger.info("\n\n>>> TEST: TaskPlanner <<<")

        planner = TaskPlanner()

        # Test plan creation
        query = "Calculate 15 times 23"
        logger.info(f"\n>>> Creating plan for: {query}")

        plan = planner.create_plan(
            query=query,
            context="",
            available_tools=[
                {"type": "function", "function": {"name": "calculator", "description": "Math calculator"}},
                {"type": "function", "function": {"name": "python_repl", "description": "Python execution"}}
            ]
        )

        logger.info(f">>> Created plan with {len(plan)} steps:")
        for step in plan:
            logger.info(f"    Step {step.get('step')}: {step.get('action')} - {step.get('description')}")

        assert isinstance(plan, list)
        # Plan might be empty if mock returns unparseable response, which falls back to single step
        if len(plan) == 0:
            logger.info(">>> Plan empty due to mock LLM response, checking fallback...")
            # Re-create with simple query to test fallback
            plan = planner.create_plan("Hello")
            assert len(plan) >= 1, "Fallback should create at least one step"

        # Test get_next_step
        completed = []
        step = planner.get_next_step(plan, completed)
        logger.info(f">>> Next step: {step}")
        assert step is not None


class TestMemoryAccessorDebug:
    """Debug tests for MemoryAccessor with logging."""

    def test_retrieve_for_query_debug(self):
        """Test MemoryAccessor.retrieve_for_query with logging"""
        logger.info("\n\n>>> TEST: MemoryAccessor.retrieve_for_query <<<")

        accessor = MemoryAccessor()

        # Store some history first
        accessor.memory.store_conversation("test_session", [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."}
        ])

        result = accessor.retrieve_for_query(
            query="programming languages",
            session_id="test_session",
            top_k=3
        )

        logger.info(f">>> Retrieved result:")
        logger.info(f"    knowledge: {result.get('knowledge', [])}")
        logger.info(f"    history_summary: {result.get('history_summary', '')}")
        logger.info(f"    related_queries: {result.get('related_queries', [])}")

        assert isinstance(result, dict)
        assert "knowledge" in result
        assert "history_summary" in result

    def test_format_context_debug(self):
        """Test MemoryAccessor.format_context with logging"""
        logger.info("\n\n>>> TEST: MemoryAccessor.format_context <<<")

        accessor = MemoryAccessor()

        retrieval_result = {
            "knowledge": ["Python is a language", "JavaScript is another"],
            "history_summary": "Recent conversation has 2 messages",
            "related_queries": ["What is Python?"]
        }

        formatted = accessor.format_context(retrieval_result)
        logger.info(f">>> Formatted context:\n{formatted}")

        assert "Python" in formatted
        assert "conversation" in formatted


if __name__ == "__main__":
    # Run tests with detailed output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
