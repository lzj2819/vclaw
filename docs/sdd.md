# VClaw 六层架构软件设计文档 (SDD)

> **版本**: 1.0  
> **日期**: 2024  
> **架构**: 六层分层架构  
> **开发方法**: TDD (Test-Driven Development)

---

## 目录

1. [架构总览](#1-架构总览)
2. [设计原则](#2-设计原则)
3. [层次结构](#3-层次结构)
4. [数据流](#4-数据流)
5. [耦合关系](#5-耦合关系)
6. [接口规范](#6-接口规范)
7. [技术栈](#7-技术栈)
8. [项目结构](#8-项目结构)
9. [TDD与SDD分工](#9-tdd与sdd分工)
10. [详细规范文档](#10-详细规范文档)

---

## 1. 架构总览

VClaw是一个六层架构的AI Agent系统，参考OpenClaw设计，采用严格的分层架构和单向依赖原则。

### 1.1 六层架构

```
┌─────────────────────────────────────────────────────────────┐
│ L1: User Interaction (用户接入层)                           │
│ 职责: 系统的"门面"，处理所有输入输出                          │
└───────────────────┬─────────────────────────────────────────┘
                    │ 直接方法调用
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ L2: Control Gateway (控制网关层)                            │
│ 职责: 系统的"关卡"，路由、鉴权、限流、会话管理                │
└───────────────────┬─────────────────────────────────────────┘
                    │ 直接方法调用
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ L3: Orchestration (逻辑编排层)                              │
│ 职责: 系统的"指挥官"，意图识别、任务拆解、ReAct循环          │
└───────────┬───────┴───────┬─────────────────────────────────┘
            │               │ 依赖注入 (DI)
            ▼               ▼
┌───────────────┐   ┌─────────────────────────────────────────┐
│ L4: Memory    │   │ L5: Tools & Capabilities               │
│ (记忆与知识层) │   │ (能力抽象层)                            │
│ 职责: RAG、   │   │ 职责: 工具定义、API封装、安全路由        │
│ 向量索引      │   └───────────────┬─────────────────────────┘
└───────────────┘                   │ 直接方法调用
                                    ▼
                    ┌─────────────────────────────────────────┐
                    │ L6: Runtime & Environment              │
                    │ (环境执行层)                            │
                    │ 职责: 沙盒、容器、文件系统、OS调用        │
                    └─────────────────────────────────────────┘
```

---

## 2. 设计原则

### 2.1 核心原则

1. **单向依赖**: 上层可调用下层，下层绝不允许调用上层
2. **接口隔离**: 层与层之间通过严格定义的接口通信
3. **依赖注入**: 使用依赖注入实现松耦合（L3通过DI使用L4、L5）
4. **测试先行**: 所有功能先写测试（TDD），再写实现
5. **安全第一**: 严格的安全控制和沙盒隔离

### 2.2 架构模式

- **分层架构 (Layered Architecture)**: 清晰的层次边界
- **依赖注入 (Dependency Injection)**: L3注入L4和L5接口
- **策略模式 (Strategy Pattern)**: 可替换的向量存储、沙盒实现
- **工厂模式 (Factory Pattern)**: 协议适配器、工具实例化

---

## 3. 层次结构

### 3.1 L1: 用户接入层 (User Interaction)

**职责**: 系统的"门面"，负责所有形式的输入与输出

**核心功能**:
- 接收并解析异构外部协议（WebSocket, Telegram API, HTTP Webhook）
- 剥离渠道特征，将原始数据标准化为统一事件格式
- 数据验证和清洗（JSON Schema校验、注入防护）
- 错误处理和重试机制

**接口**:
```python
def receive_payload(raw_data: dict) -> StandardEvent:
    """
    接收原始数据，返回标准化事件
    
    Input:  任意渠道的原始JSON
    Output: StandardEvent对象
        - channel: str        # 渠道来源
        - user_id: str        # 用户唯一标识
        - content: str        # 用户输入内容
        - timestamp: float    # 时间戳
        - metadata: dict      # 附加元数据
    """
```

**详细文档**: [L1_UserInteraction.xml](./L1_UserInteraction.xml)

---

### 3.2 L2: 控制网关层 (Control Gateway)

**职责**: 系统的"关卡"，负责路由、鉴权、限流与会话状态维护

**核心功能**:
- 身份认证与权限校验（JWT/API Key验证）
- 会话管理（Session ID生成、生命周期管理）
- 历史记录检索与拼接（滑动窗口）
- 限流控制（Token Bucket算法）
- 上下文组装（无状态Event → 有状态Context）

**接口**:
```python
def process_event(event: StandardEvent) -> SessionContext:
    """
    处理事件，返回会话上下文
    
    Input:  StandardEvent对象
    Output: SessionContext对象
        - session_id: str          # 会话唯一ID (UUID)
        - user_id: str             # 用户ID
        - current_query: str       # 当前查询
        - history: list[dict]      # 历史对话（OpenAI格式）
        - user_permissions: list   # 用户权限
        - created_at: float        # 创建时间
    """

def send_response(session_id: str, text: str) -> bool:
    """发送响应给用户"""
```

**详细文档**: [L2_ControlGateway.xml](./L2_ControlGateway.xml)

---

### 3.3 L3: 逻辑编排层 (Orchestration)

**职责**: 系统的"指挥官"，负责意图识别、任务拆解与思维链管理

**核心功能**:
- 意图识别（理解用户想要做什么）
- 任务规划（拆解复杂请求为可执行步骤）
- **ReAct循环驱动**（Thought → Action → Observation）
- LLM调用管理（对话管理、Token优化）
- 工具调用决策

**接口**:
```python
def run(context: SessionContext, 
        observation: Observation = None) -> Union[str, AgentAction]:
    """
    执行逻辑编排
    
    Input:  
        - context: SessionContext   # 会话上下文
        - observation: Observation  # 工具执行结果（ReAct循环用）
    
    Output: 
        - str: 最终回复（给用户的答案）
        - AgentAction: 工具调用指令（发给L5）
            - action: str           # 工具名称
            - action_input: dict    # 工具参数
            - thought: str          # 思考过程
    """
```

**详细文档**: [L3_Orchestration.xml](./L3_Orchestration.xml)

---

### 3.4 L4: 记忆与知识层 (Memory & Knowledge)

**职责**: 系统的"经验库"，负责RAG、向量索引与长期记忆持久化

**核心功能**:
- 文本分块（将长文档切分为语义完整片段）
- Embedding生成（文本 → 向量）
- 相似度检索（基于向量相似度）
- 长期记忆存储（持久化对话历史）
- 索引管理

**接口**:
```python
def search(query: str, top_k: int = 5, 
           filters: dict = None) -> list[str]:
    """
    检索相关记忆
    
    Input:
        - query: str        # 检索词
        - top_k: int        # 返回数量
        - filters: dict     # 过滤条件
    
    Output: 相关记忆片段列表
    """

def store(document: str, metadata: dict) -> bool:
    """存储文档"""

def store_conversation(session_id: str, 
                      messages: list[dict]) -> bool:
    """存储对话历史"""

def retrieve_history(session_id: str, 
                    limit: int = 10) -> list[dict]:
    """检索历史对话"""
```

**详细文档**: [L4_MemoryKnowledge.xml](./L4_MemoryKnowledge.xml)

---

### 3.5 L5: 能力抽象层 (Tools & Capabilities)

**职责**: 系统的"技能包"，负责工具定义、API封装与函数调用协议

**核心功能**:
- 工具注册与发现（动态加载工具）
- 参数验证（JSON Schema校验）
- 权限检查
- 工具路由（将工具名映射到实际执行器）
- 结果格式化

**支持的工具**:
- `python_repl`: 执行Python代码
- `search_web`: 网络搜索
- `file_read`: 读取文件
- `file_write`: 写入文件
- `terminal`: 执行终端命令
- `calculator`: 数学计算

**接口**:
```python
def execute(action_name: str, 
           params: dict,
           user_permissions: list[str],
           timeout: int = 30) -> Observation:
    """
    执行工具
    
    Input:
        - action_name: str       # 工具名称
        - params: dict           # 工具参数
        - user_permissions: list # 用户权限
        - timeout: int           # 超时时间
    
    Output: Observation对象
        - status: str            # "success" | "error"
        - result: str            # 执行结果
        - execution_time: float  # 执行耗时
        - metadata: dict         # 附加信息
    """

def get_available_tools(user_permissions: list[str]) -> list[dict]:
    """获取用户可用的工具列表（OpenAI格式）"""
```

**详细文档**: [L5_ToolsCapabilities.xml](./L5_ToolsCapabilities.xml)

---

### 3.6 L6: 环境执行层 (Runtime & Environment)

**职责**: 系统的"物理世界"，负责沙盒、容器、文件系统与本地OS调用

**核心功能**:
- 代码执行（在隔离环境中运行代码）
- 沙盒隔离（Docker容器或进程隔离）
- 资源限制（CPU、内存、时间配额）
- 文件系统操作（在沙盒内读写文件）
- 安全策略执行

**接口**:
```python
def run_code(language: str, 
            code: str,
            timeout: int = 30,
            environment_config: dict = None) -> ExecutionResult:
    """
    在沙盒中执行代码
    
    Input:
        - language: str          # 编程语言 (python/javascript/bash)
        - code: str              # 代码字符串
        - timeout: int           # 超时时间
        - environment_config:    # 环境配置
            - memory_limit: int  # 内存限制(MB)
            - cpu_limit: float   # CPU限制(核数)
            - enable_network: bool # 是否允许网络
    
    Output: ExecutionResult对象
        - exit_code: int         # 退出码 (0=成功)
        - stdout: str            # 标准输出
        - stderr: str            # 错误输出
        - execution_time: float  # 执行耗时
        - resource_usage: dict   # 资源使用统计
    """
```

**详细文档**: [L6_RuntimeEnvironment.xml](./L6_RuntimeEnvironment.xml)

---

## 4. 数据流

### 4.1 完整数据流

```
用户输入 → L1 → L2 → L3 → [L4/L5] → L6
                     ↑
                     └── ReAct循环 ←──┘
```

### 4.2 数据流详解

1. **L1** 接收外部输入（Telegram/WebSocket/HTTP），转换为 `StandardEvent`
2. **L2** 接收 `StandardEvent`，鉴权/限流后组装成 `SessionContext`
3. **L2** 调用 **L3.run(context)**，传递 `SessionContext`
4. **L3** 可能调用 **L4.search()** 检索相关知识
5. **L3** 进入ReAct循环：
   - 调用LLM生成 `Thought`
   - 决策：调用工具或回复用户
   - 如需调用工具，返回 `AgentAction` 给L2，L2转发给L5
6. **L5** 验证权限和参数，调用 **L6.run_code()**
7. **L6** 在沙盒中执行代码，返回 `ExecutionResult`
8. **L5** 格式化为 `Observation`，返回给L3
9. **L3** 继续ReAct循环（回到步骤5）
10. 当L3决定直接回复时，返回字符串给L2
11. **L2** 调用L1发送响应给用户

---

## 5. 耦合关系

### 5.1 耦合矩阵

| 调用方 \ 被调用方 | L1 | L2 | L3 | L4 | L5 | L6 |
|-------------------|:--:|:--:|:--:|:--:|:--:|:--:|
| **L1** | - | 直接调用 | - | - | - | - |
| **L2** | 回调 | - | 直接调用 | - | - | - |
| **L3** | - | 返回 | - | **DI** | **DI** | - |
| **L4** | - | - | - | - | - | - |
| **L5** | - | - | 返回 | - | - | 直接调用 |
| **L6** | - | - | - | - | 返回 | - |

**图例**:
- **直接调用**: 直接方法调用
- **DI**: 依赖注入（Dependency Injection）
- **回调**: 回调机制
- **返回**: 返回结果

### 5.2 耦合方式详解

#### L1 → L2
- **方式**: 直接方法调用
- **数据**: `StandardEvent` 对象
- **耦合度**: 低（仅通过数据结构通信）

#### L2 → L3
- **方式**: 直接方法调用
- **数据**: `SessionContext` 对象
- **耦合度**: 中等（传递完整上下文）

#### L3 ↔ L4, L3 ↔ L5
- **方式**: 依赖注入（Dependency Injection）
- **接口**: `MemoryInterface`, `ToolsInterface`
- **耦合度**: 低（通过接口抽象解耦）

#### L5 → L6
- **方式**: 直接方法调用
- **数据**: `ExecutionResult` 对象
- **耦合度**: 中等（安全边界）

---

## 6. 接口规范

### 6.1 数据模型

#### StandardEvent (L1 → L2)
```python
class StandardEvent(BaseModel):
    channel: str           # "telegram", "websocket", "webhook"
    user_id: str          # 用户唯一标识
    content: str          # 用户输入内容
    timestamp: float      # Unix时间戳
    metadata: dict        # 附加元数据
```

#### SessionContext (L2 → L3)
```python
class SessionContext(BaseModel):
    session_id: str       # UUID
    user_id: str         # 用户ID
    current_query: str   # 当前查询
    history: List[dict]  # 历史对话（OpenAI格式）
    user_permissions: List[str]  # ["admin", "user", ...]
    created_at: float    # 创建时间
```

#### AgentAction (L3 → L5)
```python
class AgentAction(BaseModel):
    action: str          # 工具名称
    action_input: dict   # 工具参数
    thought: str         # 思考过程（可选）
```

#### Observation (L5 → L3)
```python
class Observation(BaseModel):
    status: str          # "success" | "error"
    result: str          # 执行结果（最大10000字符）
    execution_time: float # 执行耗时
    metadata: dict       # 附加信息
```

#### ExecutionResult (L6 → L5)
```python
class ExecutionResult(BaseModel):
    exit_code: int       # 0 = 成功
    stdout: str          # 标准输出
    stderr: str          # 错误输出
    execution_time: float # 执行耗时
    resource_usage: dict  # 资源使用统计
```

### 6.2 接口定义

```python
# L4 接口 (MemoryInterface)
class MemoryInterface(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int) -> List[str]: pass
    
    @abstractmethod
    def store(self, document: str, metadata: dict) -> bool: pass

# L5 接口 (ToolsInterface)
class ToolsInterface(ABC):
    @abstractmethod
    def execute(self, action_name: str, params: dict, 
                user_permissions: list) -> Observation: pass

# L6 接口 (RuntimeInterface)
class RuntimeInterface(ABC):
    @abstractmethod
    def run_code(self, language: str, code: str, 
                 timeout: int) -> ExecutionResult: pass
```

---

## 7. 技术栈

### 7.1 核心技术

- **语言**: Python 3.11+
- **测试框架**: pytest
- **包管理**: pip + requirements.txt

### 7.2 关键库

| 类别 | 库 | 用途 |
|------|------|------|
| Web框架 | FastAPI | HTTP服务 |
| WebSocket | websockets | 实时通信 |
| 数据验证 | Pydantic | 模型定义 |
| LLM | openai | GPT-4/GPT-3.5调用 |
| 向量DB | chromadb | 向量存储和检索 |
| 分块 | langchain | 文本分块 |
| Embedding | sentence-transformers | 本地Embedding模型 |
| 容器 | docker | Docker客户端 |
| 缓存 | redis | 会话和缓存存储 |
| 限流 | py-rate-limiter | 限流算法 |
| 安全 | restrictedpython | 受限Python执行 |

---

## 8. 项目结构

```
vclaw/
├── docs/
│   ├── sdd.md                          # 本文件
│   ├── Architecture_Overview.xml       # 架构总览
│   ├── L1_UserInteraction.xml          # L1详细规范
│   ├── L2_ControlGateway.xml           # L2详细规范
│   ├── L3_Orchestration.xml            # L3详细规范
│   ├── L4_MemoryKnowledge.xml          # L4详细规范
│   ├── L5_ToolsCapabilities.xml        # L5详细规范
│   └── L6_RuntimeEnvironment.xml       # L6详细规范
│
├── src/
│   ├── __init__.py
│   ├── models.py                       # 共享数据模型
│   ├── interfaces.py                   # 接口定义
│   ├── l1_user_interaction.py          # L1实现
│   ├── l2_control_gateway.py           # L2实现
│   ├── l3_orchestration.py             # L3实现
│   ├── l4_memory.py                    # L4实现
│   ├── l5_tools.py                     # L5实现
│   └── l6_runtime.py                   # L6实现
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # pytest配置
│   ├── test_l1.py                      # L1测试
│   ├── test_l2.py                      # L2测试
│   ├── test_l3.py                      # L3测试
│   ├── test_l4.py                      # L4测试
│   ├── test_l5.py                      # L5测试
│   ├── test_l6.py                      # L6测试
│   └── test_integration.py             # 端到端测试
│
├── requirements.txt                    # 依赖列表
├── pytest.ini                          # pytest配置
└── README.md                           # 项目说明
```

---

## 9. TDD与SDD分工

### 9.1 SDD (Software Design Document)

**职责**: 架构设计和规范定义

- ✅ 定义每层职责、接口、数据结构
- ✅ 说明耦合关系和通信协议
- ✅ 作为架构蓝图和开发指南
- ✅ 记录设计决策和约束

**产出物**:
- `docs/Architecture_Overview.xml`
- `docs/L1_UserInteraction.xml` ~ `docs/L6_RuntimeEnvironment.xml`
- `docs/sdd.md`（本文档）

### 9.2 TDD (Test-Driven Development)

**职责**: 代码实现和质量保证

- ✅ 每层开发前，先写测试定义期望行为
- ✅ 通过Mock隔离依赖，专注当前层逻辑
- ✅ 测试即文档，展示如何使用该层
- ✅ Red-Green-Refactor循环

**流程**:

```
对于每一层:
1. Red:    编写失败测试（定义期望行为）
2. Verify: 运行测试，确认失败原因正确
3. Green:  编写最小实现，使测试通过
4. Verify: 运行测试，确认全部通过
5. Refactor: 优化代码，保持测试通过
6. Repeat: 下一功能
```

**产出物**:
- `tests/test_l1.py` ~ `tests/test_l6.py`（每层Mock测试）
- `tests/test_integration.py`（端到端测试）
- `src/*.py`（实现代码）

---

## 10. 详细规范文档

每层的详细规范保存在独立的XML文档中：

| 层次 | 文档路径 | 说明 |
|------|----------|------|
| L1 | [docs/L1_UserInteraction.xml](./L1_UserInteraction.xml) | 用户接入层详细规范 |
| L2 | [docs/L2_ControlGateway.xml](./L2_ControlGateway.xml) | 控制网关层详细规范 |
| L3 | [docs/L3_Orchestration.xml](./L3_Orchestration.xml) | 逻辑编排层详细规范 |
| L4 | [docs/L4_MemoryKnowledge.xml](./L4_MemoryKnowledge.xml) | 记忆与知识层详细规范 |
| L5 | [docs/L5_ToolsCapabilities.xml](./L5_ToolsCapabilities.xml) | 能力抽象层详细规范 |
| L6 | [docs/L6_RuntimeEnvironment.xml](./L6_RuntimeEnvironment.xml) | 环境执行层详细规范 |

每个XML文档包含：
1. **结构说明**: 详细组件、职责、数据流
2. **接口规范**: 完整的输入/输出定义、异常处理
3. **耦合关系**: 与上下层的耦合方式和数据格式
4. **Mock测试规范**: 详细的测试用例和TDD流程

---

## 附录

### A. 缩略语

- **TDD**: Test-Driven Development（测试驱动开发）
- **SDD**: Software Design Document（软件设计文档）
- **DI**: Dependency Injection（依赖注入）
- **RAG**: Retrieval-Augmented Generation（检索增强生成）
- **ReAct**: Reasoning and Acting（推理与行动，LLM范式）
- **RPC**: Remote Procedure Call（远程过程调用）
- **IPC**: Inter-Process Communication（进程间通信）

### B. 参考资料

- [OpenClaw Architecture](https://github.com/OpenClaw)
- [ReAct Pattern](https://arxiv.org/abs/2210.03629)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Dependency Injection](https://martinfowler.com/articles/injection.html)

---

**文档状态**: ✅ 已完成  
**下一步**: 进入实施阶段（Writing Plans + TDD实现）
