"""L4: Memory & Knowledge Layer - Vector search and memory storage."""
import hashlib
from typing import List, Dict, Any, Optional
from src.models import Document
from src.interfaces import MemoryInterface


class EmbeddingService:
    """Simple embedding service (mock for now)."""
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # Mock implementation - in production use OpenAI or local model
        return [0.1] * 1536
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [[0.1] * 1536 for _ in texts]


class TextChunker:
    """Simple text chunker."""
    
    def split(self, text: str, chunk_size: int = 1000, 
              overlap: int = 200) -> List[str]:
        """Split text into chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks


class MemoryVectorStore:
    """In-memory vector store for testing."""
    
    def __init__(self):
        self.documents = {}  # id -> {content, embedding, metadata}
    
    def add(self, doc_id: str, content: str, 
            embedding: List[float], metadata: Dict):
        """Add a document."""
        self.documents[doc_id] = {
            "content": content,
            "embedding": embedding,
            "metadata": metadata
        }
    
    def search(self, query_embedding: List[float], 
               top_k: int = 5) -> List[Dict]:
        """Search for similar documents."""
        # Simple cosine similarity (mock)
        results = []
        for doc_id, doc in self.documents.items():
            # Mock score
            score = 0.9  # In production, calculate actual similarity
            results.append({
                "content": doc["content"],
                "score": score,
                "metadata": doc["metadata"]
            })
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


class MemoryStore:
    """In-memory conversation store."""
    
    def __init__(self):
        self.conversations = {}  # session_id -> messages
    
    def save(self, session_id: str, messages: List[Dict]) -> bool:
        """Save conversation."""
        self.conversations[session_id] = messages
        return True
    
    def load(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Load conversation."""
        messages = self.conversations.get(session_id, [])
        return messages[-limit:] if messages else []


class MemoryKnowledge(MemoryInterface):
    """L4 implementation - Memory and knowledge management."""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = MemoryVectorStore()
        self.text_chunker = TextChunker()
        self.memory_store = MemoryStore()
        self.cache = {}  # Simple cache
    
    def search(self, query: str, top_k: int = 5,
               filters: Optional[Dict] = None) -> List[str]:
        """Search for relevant documents."""
        # Check cache
        cache_key = f"{query}_{top_k}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Generate embedding
        query_embedding = self.embedding_service.embed(query)
        
        # Search vector store
        results = self.vector_store.search(query_embedding, top_k)
        
        # Extract content
        contents = [r["content"] for r in results]
        
        # Cache results
        self.cache[cache_key] = contents
        
        return contents
    
    def store(self, document: str, metadata: Dict[str, Any]) -> bool:
        """Store a document."""
        # Chunk document
        chunks = self.text_chunker.split(document)
        
        # Generate embeddings
        embeddings = self.embedding_service.embed_batch(chunks)
        
        # Store each chunk
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            doc_id = f"{metadata.get('doc_id', 'unknown')}_{i}"
            self.vector_store.add(doc_id, chunk, embedding, metadata)
        
        return True
    
    def store_conversation(self, session_id: str,
                          messages: List[Dict[str, str]]) -> bool:
        """Store conversation history."""
        return self.memory_store.save(session_id, messages)
    
    def retrieve_history(self, session_id: str,
                        limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve conversation history."""
        return self.memory_store.load(session_id, limit)
