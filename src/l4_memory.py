"""L4: Memory & Knowledge Layer - Vector search, memory storage, and compression."""
import hashlib
from collections import OrderedDict
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


class MemoryCompressor:
    """Memory compressor for compressing conversation history."""

    def __init__(self, max_messages: int = 20, compression_threshold: int = 10):
        """
        Args:
            max_messages: Maximum messages before triggering compression
            compression_threshold: Number of oldest messages to compress when triggered
        """
        self.max_messages = max_messages
        self.compression_threshold = compression_threshold

    def should_compress(self, messages: List[Dict]) -> bool:
        """Check if messages should be compressed."""
        return len(messages) >= self.max_messages

    def compress(self, messages: List[Dict]) -> List[Dict]:
        """Compress messages by summarizing oldest ones.

        Returns:
            Compressed message list with:
            - A summary message at the beginning
            - Recent messages that weren't compressed
        """
        if not self.should_compress(messages):
            return messages

        # Split messages into those to compress and those to keep
        num_to_compress = len(messages) - self.compression_threshold
        messages_to_compress = messages[:num_to_compress]
        messages_to_keep = messages[num_to_compress:]

        # Generate summary of compressed messages
        summary = self._generate_summary(messages_to_compress)

        # Create compressed result
        compressed = [
            {
                "role": "system",
                "content": f"[Earlier conversation summary]: {summary}",
                "is_compressed": True,
                "original_count": len(messages_to_compress)
            }
        ]
        compressed.extend(messages_to_keep)

        return compressed

    def _generate_summary(self, messages: List[Dict]) -> str:
        """Generate a summary of messages.

        In a real implementation, this could use an LLM.
        For now, use a simple extractive summary.
        """
        if not messages:
            return ""

        # Extract key points (user questions and assistant main points)
        key_points = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            if role == "user":
                # Truncate long user messages
                if len(content) > 100:
                    content = content[:97] + "..."
                key_points.append(f"User asked: {content}")
            elif role == "assistant":
                # Extract first sentence or truncate
                first_sentence = content.split(".")[0] if "." in content else content[:100]
                if len(first_sentence) > 100:
                    first_sentence = first_sentence[:97] + "..."
                key_points.append(f"Assistant responded about: {first_sentence}")

        # Limit number of key points
        if len(key_points) > 5:
            key_points = key_points[:2] + ["..."] + key_points[-2:]

        return " | ".join(key_points)

    def get_compression_stats(self, original: List[Dict], compressed: List[Dict]) -> Dict:
        """Get compression statistics."""
        original_tokens = sum(len(m.get("content", "")) for m in original)
        compressed_tokens = sum(len(m.get("content", "")) for m in compressed)

        return {
            "original_messages": len(original),
            "compressed_messages": len(compressed),
            "original_length": original_tokens,
            "compressed_length": compressed_tokens,
            "compression_ratio": compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            "messages_summarized": len(original) - len(compressed) + 1  # +1 for summary message
        }


class MemoryStore:
    """In-memory conversation store with compression."""

    def __init__(self, compressor: MemoryCompressor = None):
        self.conversations = {}  # session_id -> messages
        self.compressor = compressor or MemoryCompressor(
            max_messages=20,
            compression_threshold=10
        )
        self.compression_stats = {}  # session_id -> compression history

    def save(self, session_id: str, messages: List[Dict]) -> bool:
        """Save conversation, with compression if needed."""
        # Check if compression is needed
        if self.compressor.should_compress(messages):
            compressed = self.compressor.compress(messages)
            stats = self.compressor.get_compression_stats(messages, compressed)

            # Store stats
            if session_id not in self.compression_stats:
                self.compression_stats[session_id] = []
            self.compression_stats[session_id].append(stats)

            self.conversations[session_id] = compressed
        else:
            self.conversations[session_id] = messages

        return True

    def load(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Load conversation."""
        messages = self.conversations.get(session_id, [])

        # If messages contain compressed summary, handle appropriately
        if messages and messages[0].get("is_compressed"):
            # Return all messages (including summary) up to limit
            return messages[-limit:] if len(messages) > limit else messages

        return messages[-limit:] if messages else []

    def get_full_history(self, session_id: str) -> List[Dict]:
        """Get full conversation history including compressed parts."""
        return self.conversations.get(session_id, [])

    def get_compression_stats(self, session_id: str) -> List[Dict]:
        """Get compression statistics for a session."""
        return self.compression_stats.get(session_id, [])

    def force_compress(self, session_id: str) -> bool:
        """Force compression of a session's history."""
        if session_id not in self.conversations:
            return False

        messages = self.conversations[session_id]
        compressed = self.compressor.compress(messages)
        stats = self.compressor.get_compression_stats(messages, compressed)

        if session_id not in self.compression_stats:
            self.compression_stats[session_id] = []
        self.compression_stats[session_id].append(stats)

        self.conversations[session_id] = compressed
        return True


class MemoryKnowledge(MemoryInterface):
    """L4 implementation - Memory and knowledge management with compression."""

    DEFAULT_CACHE_SIZE = 100  # LRU cache size limit

    def __init__(self, cache_size: int = DEFAULT_CACHE_SIZE):
        self.embedding_service = EmbeddingService()
        self.vector_store = MemoryVectorStore()
        self.text_chunker = TextChunker()
        self.memory_store = MemoryStore()
        self.cache = OrderedDict()  # LRU cache
        self.cache_size = cache_size

    def search(self, query: str, top_k: int = 5,
               filters: Optional[Dict] = None) -> List[str]:
        """Search for relevant documents with LRU caching."""
        cache_key = f"{query}_{top_k}"

        # Check cache - move to end if found (most recently used)
        if cache_key in self.cache:
            self.cache.move_to_end(cache_key)
            return self.cache[cache_key]

        # Generate embedding
        query_embedding = self.embedding_service.embed(query)

        # Search vector store
        results = self.vector_store.search(query_embedding, top_k)

        # Extract content
        contents = [r["content"] for r in results]

        # Cache results - add to end
        self.cache[cache_key] = contents

        # Evict oldest if over size limit
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)

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
        """Store conversation history with compression."""
        return self.memory_store.save(session_id, messages)

    def retrieve_history(self, session_id: str,
                        limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve conversation history."""
        return self.memory_store.load(session_id, limit)

    def get_full_history(self, session_id: str) -> List[Dict]:
        """Get full conversation history including compressed parts."""
        return self.memory_store.get_full_history(session_id)

    def compress_session(self, session_id: str) -> bool:
        """Force compression of a session's history."""
        return self.memory_store.force_compress(session_id)

    def get_compression_stats(self, session_id: str) -> List[Dict]:
        """Get compression statistics for a session."""
        return self.memory_store.get_compression_stats(session_id)
