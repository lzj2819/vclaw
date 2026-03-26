"""Tests for L4 Memory & Knowledge."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, 'src')

from src.l4_memory import MemoryKnowledge, MemoryVectorStore
from src.models import Document


class TestMemoryKnowledge:
    """Tests for L4 Memory & Knowledge."""
    
    def test_search_basic(self):
        """TC-L4-001: 向量检索基本功能"""
        # Arrange
        memory = MemoryKnowledge()
        
        # Mock embedding service
        with patch.object(memory.embedding_service, 'embed') as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            
            # Mock vector store
            with patch.object(memory.vector_store, 'search') as mock_search:
                mock_search.return_value = [
                    {"content": "Python is a programming language", "score": 0.95},
                    {"content": "JavaScript is another language", "score": 0.85}
                ]
                
                # Act
                results = memory.search("programming", top_k=2)
                
                # Assert
                assert len(results) == 2
                assert "Python" in results[0]
                mock_embed.assert_called_once_with("programming")
                mock_search.assert_called_once()
    
    def test_cache_hit(self):
        """TC-L4-002: 缓存命中"""
        # Arrange
        memory = MemoryKnowledge()
        
        # First call
        with patch.object(memory.embedding_service, 'embed') as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            with patch.object(memory.vector_store, 'search') as mock_search:
                mock_search.return_value = [{"content": "test"}]
                memory.search("test query")
        
        # Second call - should use cache
        with patch.object(memory.embedding_service, 'embed') as mock_embed:
            results = memory.search("test query")
            # Embedding should not be called again
            mock_embed.assert_not_called()
    
    def test_store_document(self):
        """TC-L4-003: 文档存储"""
        # Arrange
        memory = MemoryKnowledge()
        
        with patch.object(memory.text_chunker, 'split') as mock_split:
            mock_split.return_value = ["chunk1", "chunk2"]
            
            with patch.object(memory.embedding_service, 'embed_batch') as mock_embed:
                mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]
                
                with patch.object(memory.vector_store, 'add') as mock_add:
                    mock_add.return_value = True
                    
                    # Act
                    result = memory.store("Long document content...", {"doc_id": "123"})
                    
                    # Assert
                    assert result is True
                    mock_split.assert_called_once()
                    mock_embed.assert_called_once()
                    mock_add.assert_called()
    
    def test_store_and_retrieve_conversation(self):
        """TC-L4-005: 对话历史存储与检索"""
        # Arrange
        memory = MemoryKnowledge()
        session_id = "test-session-123"
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        # Store
        with patch.object(memory.memory_store, 'save') as mock_save:
            mock_save.return_value = True
            result = memory.store_conversation(session_id, messages)
            assert result is True
        
        # Retrieve
        with patch.object(memory.memory_store, 'load') as mock_load:
            mock_load.return_value = messages
            retrieved = memory.retrieve_history(session_id, limit=2)
            assert len(retrieved) == 2


class TestMemoryVectorStore:
    """Tests for in-memory vector store."""
    
    def test_add_and_search(self):
        """Test adding documents and searching"""
        store = MemoryVectorStore()
        
        # Add documents
        store.add("doc1", "Python programming", [0.1, 0.2, 0.3], {})
        store.add("doc2", "Java programming", [0.2, 0.3, 0.4], {})
        
        # Search
        results = store.search([0.1, 0.2, 0.3], top_k=1)
        assert len(results) == 1
        assert results[0]["content"] == "Python programming"
