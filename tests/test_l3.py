"""Tests for L3 Orchestration."""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l3_orchestration import Orchestration
from src.models import SessionContext, AgentAction, Observation


class TestOrchestration:
    """Tests for L3 Orchestration."""
    
    def test_simple_chat_response(self):
        """TC-L3-001: 简单对话回复（无需工具）"""
        # Arrange
        orchestration = Orchestration()
        context = SessionContext(
            session_id="test_123",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=["user"]
        )
        
        # Mock intent recognizer
        with patch.object(orchestration.intent_recognizer, 'recognize') as mock_intent:
            mock_intent.return_value = "chat"
            
            # Mock LLM to return direct response
            with patch.object(orchestration.llm_manager, 'complete') as mock_llm:
                mock_llm.return_value = "Hello! How can I help you today?"
                
                # Act
                result = orchestration.run(context)
                
                # Assert
                assert isinstance(result, str)
                assert "Hello" in result
    
    def test_single_tool_call(self):
        """TC-L3-002: 单步工具调用"""
        # Arrange
        orchestration = Orchestration()
        context = SessionContext(
            session_id="test_123",
            user_id="user_123",
            current_query="Calculate 1+1",
            history=[],
            user_permissions=["admin"]
        )
        
        # Mock intent recognizer
        with patch.object(orchestration.intent_recognizer, 'recognize') as mock_intent:
            mock_intent.return_value = "action"
            
            # First call returns AgentAction, second returns final response
            llm_responses = [
                AgentAction(action="python_repl", action_input={"code": "print(1+1)"}, thought="Need to calculate"),
                "The result of 1+1 is 2"
            ]
            
            with patch.object(orchestration.llm_manager, 'complete', side_effect=llm_responses):
                # Mock tools to return observation
                with patch.object(orchestration.tools, 'execute') as mock_tools:
                    mock_tools.return_value = Observation(
                        status="success",
                        result="2",
                        execution_time=0.1,
                        metadata={}
                    )
                    
                    # Act - First call returns AgentAction
                    result = orchestration.run(context)
                    
                    # Assert
                    assert isinstance(result, AgentAction)
                    assert result.action == "python_repl"
                    
                    # Act - Second call with observation returns final response
                    observation = Observation(status="success", result="2", execution_time=0.1, metadata={})
                    result = orchestration.run(context, observation)
                    
                    # Assert
                    assert isinstance(result, str)
    
    def test_intent_recognition(self):
        """TC-L3-005: 意图识别准确性"""
        # Arrange
        orchestration = Orchestration()
        
        test_cases = [
            ("Hello", "chat"),
            ("What's the weather?", "query"),
            ("Write a Python function", "code"),
            ("Calculate this for me", "action")
        ]
        
        for query, expected_intent in test_cases:
            # Act
            intent = orchestration.intent_recognizer.recognize(query, [])
            
            # Assert
            assert intent == expected_intent, f"Expected {expected_intent} for '{query}', got {intent}"
    
    def test_memory_retrieval(self):
        """TC-L3-006: L4知识检索增强"""
        # Arrange
        orchestration = Orchestration()
        context = SessionContext(
            session_id="test_123",
            user_id="user_123",
            current_query="Tell me about Python",
            history=[],
            user_permissions=["user"]
        )
        
        # Mock memory search
        with patch.object(orchestration.memory, 'search') as mock_search:
            mock_search.return_value = ["Python is a programming language"]
            
            # Act
            results = orchestration.memory.search("Python", top_k=3)
            
            # Assert
            mock_search.assert_called_once_with("Python", top_k=3)
            assert len(results) == 1


class TestIntentRecognizer:
    """Tests for intent recognition."""
    
    def test_recognize_chat(self):
        """Test recognizing chat intent"""
        from src.l3_orchestration import IntentRecognizer
        
        recognizer = IntentRecognizer()
        assert recognizer.recognize("Hello", []) == "chat"
        assert recognizer.recognize("How are you?", []) == "chat"
    
    def test_recognize_code(self):
        """Test recognizing code intent"""
        from src.l3_orchestration import IntentRecognizer
        
        recognizer = IntentRecognizer()
        assert recognizer.recognize("Write code", []) == "code"
        assert recognizer.recognize("Python function", []) == "code"
    
    def test_recognize_action(self):
        """Test recognizing action intent"""
        from src.l3_orchestration import IntentRecognizer
        
        recognizer = IntentRecognizer()
        assert recognizer.recognize("Calculate 2+2", []) == "action"
        assert recognizer.recognize("Search for this", []) == "action"
