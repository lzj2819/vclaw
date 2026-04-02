"""Tests for L3 Orchestration."""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l3_orchestration import Orchestration, TaskPlanner, MemoryAccessor
from src.models import SessionContext, AgentAction, Observation


class TestOrchestration:
    """Tests for L3 Orchestration."""

    def test_simple_chat_response(self):
        """TC-L3-001: Simple chat response (no tools needed)"""
        # Arrange
        orchestration = Orchestration()
        context = SessionContext(
            session_id="test_123",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=["user"]
        )

        # Mock task planner to return direct LLM step
        with patch.object(orchestration.task_planner, 'create_plan') as mock_plan:
            mock_plan.return_value = [
                {"step": 1, "action": "llm", "description": "Chat response", "input": {}, "depends_on": []}
            ]

            # Mock LLM to return direct response
            with patch.object(orchestration.llm_manager, 'complete') as mock_llm:
                mock_llm.return_value = "Hello! How can I help you today?"

                # Act
                result = orchestration.run(context)

                # Assert
                assert isinstance(result, str)
                assert "Hello" in result

    def test_single_tool_call(self):
        """TC-L3-002: Single tool call"""
        # Arrange
        orchestration = Orchestration()
        context = SessionContext(
            session_id="test_123",
            user_id="user_123",
            current_query="Calculate 1+1",
            history=[],
            user_permissions=["admin"]
        )

        # Mock task planner to return calculator step
        with patch.object(orchestration.task_planner, 'create_plan') as mock_plan:
            mock_plan.return_value = [
                {"step": 1, "action": "calculator", "description": "Calculate", "input": {"expression": "1+1"}, "depends_on": []}
            ]

            # Act - First call returns AgentAction
            result = orchestration.run(context)

            # Assert
            assert isinstance(result, AgentAction)
            assert result.action == "calculator"

            # Act - Second call with observation returns final response
            with patch.object(orchestration.llm_manager, 'complete') as mock_llm:
                mock_llm.return_value = "The result of 1+1 is 2"

                observation = Observation(status="success", result="2", execution_time=0.1, metadata={})
                result = orchestration.run(context, observation)

                # Assert
                assert isinstance(result, str)

    def test_task_planning(self):
        """TC-L3-005: Task planning replaces intent recognition"""
        # Arrange
        orchestration = Orchestration()

        test_queries = [
            "Hello",
            "What's the weather?",
            "Write a Python function",
            "Calculate this for me"
        ]

        for query in test_queries:
            # Act
            plan = orchestration.task_planner.create_plan(query, "", [])

            # Assert - plan should be created
            assert isinstance(plan, list)
            assert len(plan) >= 1

    def test_memory_retrieval(self):
        """TC-L3-006: L4 knowledge retrieval enhancement"""
        # Arrange
        orchestration = Orchestration()
        context = SessionContext(
            session_id="test_123",
            user_id="user_123",
            current_query="Tell me about Python",
            history=[],
            user_permissions=["user"]
        )

        # Mock memory search via MemoryAccessor
        with patch.object(orchestration.memory_accessor.memory, 'search') as mock_search:
            mock_search.return_value = ["Python is a programming language"]

            # Act
            result = orchestration.memory_accessor.retrieve_for_query(
                context.current_query,
                context.session_id
            )

            # Assert
            assert isinstance(result, dict)
            assert "knowledge" in result


class TestTaskPlanner:
    """Tests for TaskPlanner."""

    def test_create_plan_simple(self):
        """Test creating a simple plan"""
        planner = TaskPlanner()

        plan = planner.create_plan("Hello", "", [])

        assert isinstance(plan, list)
        assert len(plan) >= 1

    def test_get_next_step(self):
        """Test getting next step from plan"""
        planner = TaskPlanner()

        plan = [
            {"step": 1, "action": "llm", "description": "Step 1", "depends_on": []},
            {"step": 2, "action": "calculator", "description": "Step 2", "depends_on": [1]}
        ]

        # First step
        step = planner.get_next_step(plan, [])
        assert step["step"] == 1

        # Second step after first completed
        step = planner.get_next_step(plan, [1])
        assert step["step"] == 2


class TestMemoryAccessor:
    """Tests for MemoryAccessor."""

    def test_retrieve_for_query(self):
        """Test retrieving context for query"""
        accessor = MemoryAccessor()

        result = accessor.retrieve_for_query("test query", "test_session")

        assert isinstance(result, dict)
        assert "knowledge" in result
        assert "history_summary" in result
        assert "related_queries" in result

    def test_format_context(self):
        """Test formatting retrieved context"""
        accessor = MemoryAccessor()

        retrieval_result = {
            "knowledge": ["Item 1", "Item 2"],
            "history_summary": "2 messages",
            "related_queries": ["Previous query"]
        }

        formatted = accessor.format_context(retrieval_result)

        assert "Item 1" in formatted
        assert "messages" in formatted
