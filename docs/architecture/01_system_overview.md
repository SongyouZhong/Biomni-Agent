# Biomni-Agent 系统架构总览

## 1. 架构演进背景

在重构之前，Biomni-Agent 采用的是高度耦合的单体架构。前端逻辑、API 接口、LangChain/LangGraph Agent 规划器、大语言模型交互，以及底层的生物信息学代码执行环境全部运行在一个进程和统一的 Python 环境中。这种设计不仅难以扩展和维护，更存在严重的**安全隐患**：大模型生成的任何代码都会通过 `exec()` 直接在宿主机上运行，极其危险。

为了适应未来 AI-Driven Drug Discovery (AIDD) 的高频计算任务和科学 Agent 开发，我们将架构升级为了**现代微服务架构**。

## 2. 核心微服务模块

重构后的系统被解耦为三个主要的服务层级：

1. **API 网关层 (API Gateway)**
   - 负责接收客户端的 Restful HTTP 或 WebSocket 流式请求。
   - 负责管理并发，避免长耗时的 Agent 规划阻塞整个系统的事件循环。
2. **智能规划层 (Agent Core)**
   - 包含 `A1` Agent，负责理解用户意图、检索相关工具、拆解任务步骤。
   - 仅负责“思考”和“下发指令”，不再负责实际执行危险代码。
3. **沙箱执行引擎 (Sandbox Executor)**
   - 运行在完全隔离的 Docker 容器中。
   - 拥有上百个针对生物信息学和 AIDD 优化的依赖库（由 micromamba 管理）。
   - 通过 RPC 接口接收并安全执行大模型生成的 Python 代码，将标准输出、标准错误和生成的图片返回给上游。

## 3. 全局架构与流程图

下图展示了重构后 Biomni-Agent 微服务系统的完整请求处理链路：

```mermaid
graph TD
    %% 外部交互
    Client([Web UI / API Client])

    %% API网关层
    subgraph GatewayLayer ["1. API 网关层 (Host OS)"]
        FastAPI["API Gateway (FastAPI:8080)"]
        WS_Stream["WebSocket Stream Handler"]
        REST_API["REST /chat Handler"]
        ThreadExecutor["Thread Pool / Asyncio Queue"]
        
        FastAPI --> WS_Stream
        FastAPI --> REST_API
        WS_Stream <--> ThreadExecutor
    end

    %% Agent Core 层
    subgraph AgentLayer ["2. 智能规划层 (Conda: biomni_agent)"]
        A1_Agent["A1 Agent Planner (LangGraph)"]
        LLM_Client["LLM API Client"]
        ToolRegistry["Tool Registry / Retriever"]
        
        ThreadExecutor -->|实例化并调用 go_stream()| A1_Agent
        A1_Agent <-->|获取系统 Prompt & 检索| ToolRegistry
        A1_Agent <-->|Prompt / Token 流| LLM_Client
    end

    %% 本地 LLM
    subgraph LLMLayer ["AI Model Serving"]
        vLLM["Local vLLM Server (Port: 8000)<br>Qwen3.6-35B"]
        LLM_Client <-->|OpenAI API Format| vLLM
    end

    %% Sandbox 层
    subgraph SandboxLayer ["3. 沙箱执行层 (Docker Container)"]
        SandboxAPI["Sandbox Server (FastAPI:8081)"]
        PythonEnv["Isolated Python Runtime<br>(Conda: biomni_runtime)"]
        PlotIntercept["Matplotlib Interceptor"]
        
        SandboxAPI -->|exec() 隔离执行| PythonEnv
        PythonEnv --> PlotIntercept
        PlotIntercept -.->|Base64 编码| SandboxAPI
    end

    %% 共享存储
    SharedData[(Shared Data Volume<br>./data)]

    %% 跨层调用连线
    Client <-->|JSON Stream| FastAPI
    A1_Agent -->|RPC HTTP POST /execute| SandboxAPI
    PythonEnv <-->|读写数据| SharedData
    AgentLayer <-->|读写状态| SharedData

    classDef gateway fill:#f9f2f4,stroke:#d9534f,stroke-width:2px;
    classDef agent fill:#f0f9ff,stroke:#0284c7,stroke-width:2px;
    classDef sandbox fill:#f0fdf4,stroke:#16a34a,stroke-width:2px;
    
    class GatewayLayer gateway;
    class AgentLayer agent;
    class SandboxLayer sandbox;
```

## 4. 链路执行时序说明

1. **连接建立**：用户通过 WebSocket 连接至网关 `/api/v1/chat/stream`，并发送包含任务指令的 `ChatRequest`。
2. **异步中转**：API 网关启动后台线程，实例化并初始化 `A1` Agent，网关开始轮询 `asyncio.Queue` 中的流数据。
3. **意图规划**：Agent 请求本地 `vLLM` 大模型进行思考，根据工具库决定执行步骤，同时不断 `yield` 思考过程供网关推送给客户端。
4. **沙箱调用**：当模型决定执行一段 Python 脚本时，Agent 通过 HTTP POST 将代码发送至 `http://localhost:8081/execute`。
5. **代码执行**：沙箱环境中的 `server.py` 接收代码，捕获 `stdout/stderr`，并在遇到绘图指令时将图像转码为 Base64。
6. **结果返回**：沙箱将执行日志返回给 Agent，Agent 汇总结果后，产生最终答案，由网关标记为 `completed` 后断开连接。
