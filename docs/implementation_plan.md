# VClaw 六层架构实施计划

> **Goal**: 实现VClaw六层架构，每层先编写Mock测试，再实现功能，确保六层能顺利跑通  
> **Architecture**: 分层架构 + 依赖注入  
> **Tech Stack**: Python 3.11+, pytest, pip  
> **Method**: TDD (Test-Driven Development) - Red-Green-Refactor

---

## 实施策略

### 依赖顺序
由于层间存在依赖关系，建议按以下顺序实现：

```
Phase 1: 基础层（无依赖）
  L4 (Memory) → L6 (Runtime)
  
Phase 2: 中间层（依赖基础层）
  L5 (Tools) → L2 (Gateway)
  
Phase 3: 核心层（依赖中间层）
  L3 (Orchestration)
  
Phase 4: 接入层（依赖所有层）
  L1 (User Interaction)
  
Phase 5: 集成测试
  端到端测试
```

### TDD流程（每层）

```
对于每个功能:
  1. Red:    编写测试，验证期望行为（测试失败）
  2. Verify: 运行测试，确认失败原因正确
  3. Green:  编写最小实现，使测试通过
  4. Verify: 运行测试，确认全部通过
  5. Refactor: 优化代码，保持测试通过
  6. Commit: 提交代码
```

---

## Phase 1: 基础层实现

### Task 1: 项目初始化和共享模块

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `src/__init__.py`
- Create: `src/models.py`
- Create: `src/interfaces.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Steps:**

#### Step 1: 创建项目结构

```bash
mkdir -p src tests
touch src/__init__.py tests/__init__.py
```

#### Step 2: 编写 requirements.txt

```
# Core
pydantic>=2.0.0
python-dotenv>=1.0.0

# Web
fastapi>=0.104.0
websockets>=12.0
uvicorn>=0.24.0

# AI/LLM
openai>=1.0.0
anthropic>=0.8.0

# Vector DB
chromadb>=0.4.0
sentence-transformers>=2.2.0

# Memory/Cache
redis>=5.0.0

# Security
restrictedpython>=7.0
pyjwt>=2.8.0

# Rate Limiting
py-rate-limiter>=3.0.0

# Docker
docker>=7.0.0

# Utils
psutil>=5.9.0
aiohttp>=3.9.0
python-telegram-bot>=20.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.12.0
```

**Run:** 无需运行，保存文件即可

#### Step 3: 配置 pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
asyncio_mode = auto
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
```

#### Step 4: 编写数据模型 (src/models.py)

```python
"""Shared data models for all layers."""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


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
```

**Run:** 
```bash
python -c "from src.models import StandardEvent; print('Models OK')"
```
**Expected:** `Models OK`

#### Step 5: 编写接口定义 (src/interfaces.py)

```python
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
```

**Run:**
```bash
python -c "from src.interfaces import MemoryInterface; print('Interfaces OK')"
```
**Expected:** `Interfaces OK`

#### Step 6: 提交

```bash
git add .
git commit -m "chore: project initialization with models and interfaces"
```

---

### Task 2: L6 - 环境执行层 (Runtime & Environment)

**Files:**
- Create: `src/l6_runtime.py`
- Create: `tests/test_l6.py`

**Goal**: 实现代码在沙盒中的安全执行

#### Step 1: 编写测试 (Red)

```python
# tests/test_l6.py
import pytest
from unittest.mock import Mock, patch
from src.l6_runtime import RuntimeEnvironment, ProcessSandbox
from src.models import ExecutionResult


class TestRuntimeEnvironment:
    """Tests for L6 Runtime Environment."""
    
    def test_python_execution_success(self):
        """TC-L6-001: Python代码执行成功"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "print('Hello World')"
        
        # Act
        result = runtime.run_code("python", code, timeout=30)
        
        # Assert
        assert result.exit_code == 0
        assert "Hello World" in result.stdout
        assert result.stderr == ""
        assert result.execution_time > 0
    
    def test_python_execution_error(self):
        """TC-L6-002: 代码执行出错"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "1/0"  # Division by zero
        
        # Act
        result = runtime.run_code("python", code)
        
        # Assert
        assert result.exit_code != 0
        assert "ZeroDivisionError" in result.stderr
    
    def test_timeout(self):
        """TC-L6-003: 超时控制"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "import time; time.sleep(10)"  # Infinite sleep
        
        # Act & Assert
        with pytest.raises(ExecutionTimeoutError):
            runtime.run_code("python", code, timeout=1)
    
    def test_unsupported_language(self):
        """TC-L6-004: 不支持的语言"""
        # Arrange
        runtime = RuntimeEnvironment()
        
        # Act & Assert
        with pytest.raises(UnsupportedLanguageError):
            runtime.run_code("ruby", "puts 'hello'")
    
    def test_resource_limits(self):
        """TC-L6-005: 资源限制"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "x = 'a' * 1000000000"  # Try to allocate huge memory
        config = {"memory_limit": 100}  # 100MB
        
        # Act & Assert
        with pytest.raises(ResourceExceededError):
            runtime.run_code("python", code, environment_config=config)
    
    def test_security_violation(self):
        """TC-L6-006: 安全策略执行"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "import os; os.system('rm -rf /')"  # Dangerous code
        
        # Act & Assert
        with pytest.raises(SecurityViolationError):
            runtime.run_code("python", code)
    
    def test_output_truncation(self):
        """TC-L6-007: 输出截断"""
        # Arrange
        runtime = RuntimeEnvironment()
        code = "print('x' * 20000)"  # Generate 20KB output
        
        # Act
        result = runtime.run_code("python", code)
        
        # Assert
        assert len(result.stdout) <= 10000
        assert "[Output truncated" in result.stdout or len(result.stdout) == 10000


class TestProcessSandbox:
    """Tests for ProcessSandbox implementation."""
    
    def test_sandbox_creation(self):
        """Test sandbox environment creation"""
        sandbox = ProcessSandbox()
        env_id = sandbox.create("test_env")
        assert env_id is not None
        sandbox.destroy(env_id)
    
    def test_sandbox_isolation(self):
        """Test sandbox isolation - cannot access outside files"""
        sandbox = ProcessSandbox()
        env_id = sandbox.create("test_env")
        
        # Try to read a file outside sandbox
        result = sandbox.execute(env_id, 
                                 ["python", "-c", "open('/etc/passwd').read()"])
        assert result.exit_code != 0  # Should fail
        
        sandbox.destroy(env_id)
```

**Run:**
```bash
pytest tests/test_l6.py -v
```
**Expected:** 所有测试失败（ImportError或NameError）

#### Step 2: 实现最小代码 (Green)

```python
# src/l6_runtime.py
"""L6: Runtime & Environment Layer - Sandbox code execution."""
import subprocess
import tempfile
import os
import signal
from typing import Optional, Dict, Any
from pathlib import Path
from src.models import ExecutionResult
from src.interfaces import RuntimeInterface


class ExecutionTimeoutError(Exception):
    """Raised when code execution times out."""
    pass


class UnsupportedLanguageError(Exception):
    """Raised when language is not supported."""
    pass


class ResourceExceededError(Exception):
    """Raised when resource limits are exceeded."""
    pass


class SecurityViolationError(Exception):
    """Raised when code violates security policy."""
    pass


class SandboxCreationError(Exception):
    """Raised when sandbox creation fails."""
    pass


class ProcessSandbox:
    """Process-based sandbox for code execution."""
    
    def __init__(self, base_dir: str = "/tmp/sandbox"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.environments = {}
    
    def create(self, environment_id: str) -> str:
        """Create a new sandbox environment."""
        env_path = self.base_dir / environment_id
        env_path.mkdir(exist_ok=True)
        self.environments[environment_id] = env_path
        return environment_id
    
    def destroy(self, environment_id: str) -> bool:
        """Destroy a sandbox environment."""
        if environment_id in self.environments:
            env_path = self.environments[environment_id]
            # Clean up files
            import shutil
            if env_path.exists():
                shutil.rmtree(env_path)
            del self.environments[environment_id]
            return True
        return False
    
    def execute(self, environment_id: str, command: list, 
                timeout: int = 30) -> ExecutionResult:
        """Execute a command in the sandbox."""
        env_path = self.environments.get(environment_id)
        if not env_path:
            raise SandboxCreationError(f"Environment {environment_id} not found")
        
        try:
            result = subprocess.run(
                command,
                cwd=env_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return ExecutionResult(
                exit_code=result.returncode,
                stdout=result.stdout[:10000],  # Truncate
                stderr=result.stderr[:10000],
                execution_time=0.0,  # Simplified
                resource_usage={}
            )
        except subprocess.TimeoutExpired:
            raise ExecutionTimeoutError(f"Execution timed out after {timeout}s")


class RuntimeEnvironment(RuntimeInterface):
    """L6 implementation - Runtime environment management."""
    
    SUPPORTED_LANGUAGES = {"python", "javascript", "bash"}
    FORBIDDEN_MODULES = {"os.system", "subprocess", "__import__"}
    
    def __init__(self):
        self.sandbox = ProcessSandbox()
    
    def run_code(self, language: str, code: str, timeout: int = 30,
                 environment_config: Optional[Dict] = None) -> ExecutionResult:
        """Execute code in sandbox."""
        # Validate language
        if language not in self.SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(f"Language {language} not supported")
        
        # Security check
        self._check_security(code)
        
        # Create sandbox
        env_id = self.sandbox.create(f"env_{id(code)}")
        
        try:
            # Write code to file
            if language == "python":
                file_path = self.sandbox.environments[env_id] / "script.py"
                file_path.write_text(code)
                command = ["python", str(file_path)]
            elif language == "javascript":
                file_path = self.sandbox.environments[env_id] / "script.js"
                file_path.write_text(code)
                command = ["node", str(file_path)]
            elif language == "bash":
                file_path = self.sandbox.environments[env_id] / "script.sh"
                file_path.write_text(code)
                command = ["bash", str(file_path)]
            
            # Execute
            result = self.sandbox.execute(env_id, command, timeout)
            return result
            
        except subprocess.TimeoutExpired:
            raise ExecutionTimeoutError(f"Execution timed out after {timeout}s")
        finally:
            # Cleanup
            self.sandbox.destroy(env_id)
    
    def _check_security(self, code: str):
        """Check code for security violations."""
        for forbidden in self.FORBIDDEN_MODULES:
            if forbidden in code:
                raise SecurityViolationError(f"Forbidden module: {forbidden}")
```

**Run:**
```bash
pytest tests/test_l6.py -v
```
**Expected:** 大部分测试通过，部分可能需要调整

#### Step 3: 优化代码 (Refactor)

添加更多异常处理、日志记录、资源监控等。

#### Step 4: 提交

```bash
git add .
git commit -m "feat(L6): implement runtime environment with sandbox"
```

---

### Task 3: L4 - 记忆与知识层 (Memory & Knowledge)

**Files:**
- Create: `src/l4_memory.py`
- Create: `tests/test_l4.py`

**Goal**: 实现向量检索和记忆存储

#### Step 1: 编写测试 (Red)

```python
# tests/test_l4.py
import pytest
from unittest.mock import Mock, patch, MagicMock
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
                    mock_add.assert_called_once()
    
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
```

**Run:**
```bash
pytest tests/test_l4.py -v
```
**Expected:** 所有测试失败

#### Step 2: 实现最小代码 (Green)

```python
# src/l4_memory.py
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
```

**Run:**
```bash
pytest tests/test_l4.py -v
```
**Expected:** 大部分测试通过

#### Step 3: 提交

```bash
git add .
git commit -m "feat(L4): implement memory and knowledge layer"
```

---

### Task 4: L5 - 能力抽象层 (Tools & Capabilities)

**Files:**
- Create: `src/l5_tools.py`
- Create: `tests/test_l5.py`

**Goal**: 实现工具路由和安全控制

#### Step 1: 编写测试

```python
# tests/test_l5.py
import pytest
from unittest.mock import Mock, patch
from src.l5_tools import ToolsCapabilities
from src.models import Observation


class TestToolsCapabilities:
    """Tests for L5 Tools & Capabilities."""
    
    def test_tool_execution_success(self):
        """TC-L5-001: 工具执行成功"""
        # Arrange
        tools = ToolsCapabilities()
        
        # Mock L6
        mock_result = Mock()
        mock_result.exit_code = 0
        mock_result.stdout = "2"
        mock_result.stderr = ""
        mock_result.execution_time = 0.1
        
        with patch.object(tools.runtime, 'run_code', return_value=mock_result):
            # Act
            result = tools.execute(
                "python_repl",
                {"code": "print(1+1)"},
                user_permissions=["admin"],
                timeout=30
            )
            
            # Assert
            assert result.status == "success"
            assert "2" in result.result
            assert result.execution_time > 0
    
    def test_parameter_validation_failure(self):
        """TC-L5-002: 参数验证失败"""
        # Arrange
        tools = ToolsCapabilities()
        
        # Act & Assert
        with pytest.raises(ValidationError):
            tools.execute(
                "python_repl",
                {},  # Missing required 'code' parameter
                user_permissions=["admin"]
            )
    
    def test_permission_denied(self):
        """TC-L5-003: 权限不足被拒绝"""
        # Arrange
        tools = ToolsCapabilities()
        
        # Act & Assert
        with pytest.raises(PermissionDeniedError):
            tools.execute(
                "python_repl",
                {"code": "print('hello')"},
                user_permissions=["guest"]  # Guest cannot execute code
            )
    
    def test_tool_not_found(self):
        """TC-L5-004: 工具不存在"""
        # Arrange
        tools = ToolsCapabilities()
        
        # Act & Assert
        with pytest.raises(ToolNotFoundError):
            tools.execute(
                "nonexistent_tool",
                {},
                user_permissions=["admin"]
            )
    
    def test_execution_timeout(self):
        """TC-L5-005: 执行超时"""
        # Arrange
        tools = ToolsCapabilities()
        
        with patch.object(tools.runtime, 'run_code') as mock_run:
            from src.l6_runtime import ExecutionTimeoutError
            mock_run.side_effect = ExecutionTimeoutError("Timeout")
            
            # Act & Assert
            with pytest.raises(ExecutionTimeoutError):
                tools.execute(
                    "python_repl",
                    {"code": "while True: pass"},
                    user_permissions=["admin"],
                    timeout=1
                )
    
    def test_result_formatting(self):
        """TC-L5-006: 结果格式化"""
        # Arrange
        tools = ToolsCapabilities()
        
        # Mock L6 with long output
        mock_result = Mock()
        mock_result.exit_code = 0
        mock_result.stdout = "x" * 15000  # 15KB output
        mock_result.stderr = ""
        mock_result.execution_time = 0.5
        
        with patch.object(tools.runtime, 'run_code', return_value=mock_result):
            # Act
            result = tools.execute(
                "python_repl",
                {"code": "print('x' * 15000)"},
                user_permissions=["admin"]
            )
            
            # Assert
            assert len(result.result) <= 10000
            assert result.metadata.get("truncated") is True
    
    def test_get_available_tools(self):
        """TC-L5-007: 获取可用工具列表"""
        # Arrange
        tools = ToolsCapabilities()
        
        # Act
        available = tools.get_available_tools(["user"])
        
        # Assert
        assert isinstance(available, list)
        # Should only include tools user has permission for
        tool_names = [t.get("function", {}).get("name") for t in available]
        assert "calculator" in tool_names  # User can use calculator
```

#### Step 2: 实现代码

```python
# src/l5_tools.py
"""L5: Tools & Capabilities Layer - Tool routing and security."""
from typing import List, Dict, Any
from src.models import Observation
from src.interfaces import ToolsInterface, RuntimeInterface
from src.l6_runtime import RuntimeEnvironment


class ToolNotFoundError(Exception):
    """Raised when tool is not found."""
    pass


class ValidationError(Exception):
    """Raised when parameter validation fails."""
    pass


class PermissionDeniedError(Exception):
    """Raised when user lacks permission."""
    pass


class ExecutionTimeoutError(Exception):
    """Raised when execution times out."""
    pass


class Tool:
    """Tool definition."""
    
    def __init__(self, name: str, description: str, 
                 parameters: Dict, required_permission: str):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required_permission = required_permission


class ToolsCapabilities(ToolsInterface):
    """L5 implementation - Tools and capabilities management."""
    
    TOOL_DEFINITIONS = {
        "python_repl": Tool(
            name="python_repl",
            description="Execute Python code",
            parameters={
                "code": {"type": "string", "description": "Python code to execute"}
            },
            required_permission="execute_code"
        ),
        "calculator": Tool(
            name="calculator",
            description="Perform mathematical calculations",
            parameters={
                "expression": {"type": "string", "description": "Math expression"}
            },
            required_permission="none"
        ),
        "search_web": Tool(
            name="search_web",
            description="Search the web",
            parameters={
                "query": {"type": "string", "description": "Search query"}
            },
            required_permission="web_access"
        )
    }
    
    def __init__(self, runtime: RuntimeInterface = None):
        self.runtime = runtime or RuntimeEnvironment()
    
    def execute(self, action_name: str, params: Dict[str, Any],
                user_permissions: List[str], timeout: int = 30) -> Observation:
        """Execute a tool."""
        # Find tool
        tool = self.TOOL_DEFINITIONS.get(action_name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{action_name}' not found")
        
        # Check permission
        if tool.required_permission != "none":
            if tool.required_permission not in user_permissions and "admin" not in user_permissions:
                raise PermissionDeniedError(
                    f"Permission '{tool.required_permission}' required for tool '{action_name}'"
                )
        
        # Validate parameters
        self._validate_params(params, tool.parameters)
        
        # Execute
        if action_name == "python_repl":
            return self._execute_python(params, timeout)
        elif action_name == "calculator":
            return self._execute_calculator(params)
        elif action_name == "search_web":
            return self._execute_search(params)
        else:
            raise ToolNotFoundError(f"Execution logic not implemented for '{action_name}'")
    
    def _validate_params(self, params: Dict, schema: Dict):
        """Validate parameters against schema."""
        for param_name, param_def in schema.items():
            if param_name not in params:
                raise ValidationError(f"Missing required parameter: {param_name}")
    
    def _execute_python(self, params: Dict, timeout: int) -> Observation:
        """Execute Python code."""
        code = params.get("code", "")
        
        result = self.runtime.run_code("python", code, timeout)
        
        # Format result
        output = result.stdout
        if result.stderr:
            output += f"\n[Error] {result.stderr}"
        
        # Truncate if needed
        truncated = len(output) > 10000
        if truncated:
            output = output[:9970] + "\n[Output truncated...]"
        
        return Observation(
            status="success" if result.exit_code == 0 else "error",
            result=output,
            execution_time=result.execution_time,
            metadata={
                "exit_code": result.exit_code,
                "truncated": truncated
            }
        )
    
    def _execute_calculator(self, params: Dict) -> Observation:
        """Execute calculator."""
        expression = params.get("expression", "")
        try:
            # Safe evaluation (simple math only)
            result = eval(expression, {"__builtins__": {}}, {})
            return Observation(
                status="success",
                result=str(result),
                execution_time=0.0,
                metadata={}
            )
        except Exception as e:
            return Observation(
                status="error",
                result=str(e),
                execution_time=0.0,
                metadata={}
            )
    
    def _execute_search(self, params: Dict) -> Observation:
        """Execute web search."""
        # Mock implementation
        query = params.get("query", "")
        return Observation(
            status="success",
            result=f"Search results for: {query}\n[Mock results]",
            execution_time=0.5,
            metadata={}
        )
    
    def get_available_tools(self, user_permissions: List[str]) -> List[Dict]:
        """Get list of available tools for user."""
        available = []
        
        for tool in self.TOOL_DEFINITIONS.values():
            # Check permission
            if tool.required_permission == "none" or \
               tool.required_permission in user_permissions or \
               "admin" in user_permissions:
                available.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters
                    }
                })
        
        return available
```

#### Step 3: 提交

```bash
git add .
git commit -m "feat(L5): implement tools and capabilities layer"
```

---

## Phase 2: 中间层实现

### Task 5: L2 - 控制网关层 (Control Gateway)

**Files:**
- Create: `src/l2_control_gateway.py`
- Create: `tests/test_l2.py`

**Goal**: 实现认证、限流、会话管理

（按照上述模式继续实现L2、L3、L1...）

---

## 快速执行命令

要快速开始实施，请按顺序执行：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行所有测试
pytest tests/ -v

# 3. 每层实现后提交
git add . && git commit -m "feat(LX): description"
```

---

## 下一步

完成以上计划后，我们将：
1. ✅ 完成L2、L3、L1的实现
2. ✅ 编写端到端集成测试
3. ✅ 验证六层能顺利跑通
4. ✅ 添加文档和示例

**准备开始实施吗？** 我可以帮您执行Phase 1的任何任务。
