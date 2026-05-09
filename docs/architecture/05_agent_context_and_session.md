# Agent 机制与上下文会话管理

本文档详细介绍了 Biomni-Agent 项目中核心代理 (Agent) 的运行机制，以及它在系统各层中是如何处理会话 (Session) 和上下文 (Context) 的。

## 1. Agent 核心运行机制

Biomni-Agent 并不是通过简单的 while 循环和字符串匹配来执行任务的，而是深度集成了 **LangGraph** 和 **LangChain** 框架。

### 1.1 LangGraph 状态机编排
生物信息学的数据处理通常包含非常复杂的长逻辑链路（例如：读取文件 -> 写代码过滤数据 -> 报错 -> 捕获报错信息 -> 重新写代码 -> 画图）。为了使大语言模型 (LLM) 能够在这条长链路中不迷失，项目使用了 LangGraph 的图引擎 (`StateGraph`) 进行编排：

- **状态定义 (`AgentState`)**: 系统通过 `TypedDict` 定义了标准化的全局状态字典，其中最核心的字段是 `messages` (消息列表，包含 `HumanMessage`, `AIMessage`, `ToolMessage` 等)。
- **节点路由**: LLM 被包装为图中的节点。模型在决定调用工具后，执行流会转入工具节点执行代码，产生的终端输出 (`Observation`) 会被包装成 `ToolMessage` 重新压入 `messages` 中，随后流转回 LLM 节点进行进一步推理。
- **循环与边界**: 通过设置 `recursion_limit: 500`，Agent 被允许在单次任务中进行多达 500 次的内部思考和工具调用，直到推理出最终结论（打上 `<solution>` 标签）才会跳出循环。

### 1.2 动态工具与能力挂载 (`ToolRegistry`)
Agent 的能力是高度动态的，通过 `ToolRegistry` 进行管理：
- **函数注入**: Python 原生函数或脚本可通过 `add_tool` 注册。系统会自动提取函数的 docstring 和参数列表，利用内置的 `function_to_api_schema` 和 `api_schema_to_langchain_tool` 转换为 LangChain 标准工具对象。
- **MCP 协议支持**: 支持通过 `add_mcp` 方法动态读取 YAML 配置，同步连接标准的 MCP (Model Context Protocol) 服务器，极大地扩展了工具生态。

---

## 2. 上下文与内存管理 (Context & Memory)

在多轮对话以及长时间任务的上下文中，Biomni-Agent 的设计采取了**“执行时记忆”与“接口级无状态”相结合**的策略。

### 2.1 单次任务内部上下文 (`MemorySaver`)
当 Agent 接收到一个复杂的命令开始执行时（进入 `A1.go()` 或 `A1.go_stream()` 方法）：
- 系统实例化了 LangGraph 的纯内存检查点对象：`self.checkpointer = MemorySaver()`。
- 配置字典硬编码了线程 ID：`config = {"recursion_limit": 500, "configurable": {"thread_id": 42}}`。
- **作用域**：这个 `MemorySaver` **仅存活于当前这次问题求解的整个循环生命周期内**。无论 LLM 在内部自己调用了多少次 Sandbox 运行代码、产生多少报错日志，这些内部上下文都会被完好地保存在这次图遍历的 `MemorySaver` 中。

### 2.2 跨请求/跨轮次上下文 (API 网关无状态化)
对于整个后端系统（`backend/main.py`）而言，系统是**完全无状态 (Stateless)** 的：
- 每当客户端发起一次 REST API 请求 (`/api/v1/chat`) 或建立 WebSocket 连接时，API 网关服务 `BiomniAgentService` 都会通过 `_create_agent` **重新实例化一个全新的 `A1` Agent 对象**。
- **结论**：后端不使用 Redis、PostgreSQL 等数据库来存储跨 HTTP 请求的 Session 会话。上文提到的 `thread_id=42` 也因为每次都重新 `new` 了一个独立的 `MemorySaver` 而不具备跨请求溯源的作用。

---

## 3. 会话管理方案对比 (API vs UI)

由于后端的无状态设计，针对不同的使用场景，会话状态的管理责任被转移到了客户端层面。

### 3.1 开发者 API 调用 (API Client)
如果是通过 API 集成 Biomni-Agent：
- **无多轮记忆**：单次发送 `query="提取基因X"` 会得到结果；紧接着发送 `query="把它画出来"` 时，系统不知道“它”是指代什么。
- **管理方案**：客户端开发者必须自己在本地或者自己的后端维护 Message History，然后在发起下一次请求时，将之前的对话记录拼接并压缩到 `query` 参数中发送。

### 3.2 Gradio 演示界面 (UI 层)
在 `biomni/agent/a1.py` 中内置的 `launch_gradio_demo` 模块实现了一套纯前端视角的会话管理逻辑：
- 界面组件持有一个局部的历史状态变量（在代码中为实例变量 `self.main_history_copy = []`）。
- 每当用户在输入框打字并发送时，UI 层代码会将新消息 append 到这个列表中。
- 在准备调用底层 `A1` 图引擎之前，代码会迭代这个完整的历史数组，将它们手动重新组装成 LangChain 的 `HumanMessage` 和 `AIMessage` 对象列表：
  ```python
  inputs = {"messages": agent_messages, "next_step": None}
  ```
- 然后将携带了**完整历史对话**的 `inputs` 一次性喂给（刚刚初始化的）底层图引擎去执行。

## 4. 长耗时任务管理机制

针对长耗时任务（如执行长达数小时的生信分析流水线），Biomni-Agent 并**不具备原生的 Agent 休眠或异步后台轮询机制**，而是采取了**“同步阻塞 + 强制超时熔断”**的策略：

### 4.1 同步阻塞与超时熔断
- **安全沙盒限制**：所有代码/工具的执行（如 Python、R、Bash 脚本）均由 `run_with_timeout` 函数（基于 `threading.Thread.join`）包裹。
- **默认时限**：系统默认代码执行的超时时间通常为 **10 分钟（600秒）**。
- **执行表现**：当进入工具执行节点时，LangGraph 状态机处于同步阻塞状态等待结果返回。若执行超过 10 分钟，线程将会中止等待，并将硬编码的超时报错（`ERROR: Code execution timed out after 600 seconds...`）包装为 `ToolMessage` 强制返回给大模型。

### 4.2 超长任务的降级处理（大模型变通策略）
因为框架不支持将 Agent 任务直接推入后台挂起，面对真正需要运行几个小时的任务时，系统依赖大模型自发的**变通策略**来突破时间限制：
- 模型在预判任务耗时，或收到超时报错后，会自动编写带有 `nohup ... &` 的后台运行 Bash 脚本。
- 通过把重负载进程转移给 Linux 系统后台，当前节点的沙盒执行会立刻得到返回结果（成功提交）。
- 随后，大模型会通过循环发起新的工具调用（如使用 `cat nohup.out` 或 `tail`）去定期轮询日志状态，直至任务完成。

---

## 5. 意图识别与动态工具检索 (Tool RAG)

Biomni-Agent 包含了 350+ 个垂直领域的生物学科研工具（分布在 `biomni/tool/` 下的各个文件中）。如果将这些工具的 JSON Schema 一次性全部注入到 System Prompt 中，不仅会引发严重的上下文爆炸（Token 溢出）导致成本激增，还会让大模型注意力分散、产生幻觉。

为了解决海量工具的挂载问题，系统在 `biomni/model/retriever.py` 中实现了一套纯基于 LLM Prompt 路由的**动态工具检索（Prompt-based Retrieval）机制**。其底层的完整数据流和处理细节如下：

### 5.1 全量资源格式化与打宽
在进入主 LangGraph 节点之前，`ToolRetriever._format_resources_for_prompt` 方法会将系统当前挂载的所有可用资源池进行降维打平，转化为带有数字索引的纯文本列表。资源不仅包含普通函数，还横向覆盖了数据湖和经验文档：
- **TOOLS**：各类普通函数工具（如 `search_literature`, `analyze_rna_structure`）。
- **DATA_LAKE**：数据湖中的数据集描述。
- **LIBRARIES**：可用的第三方软件库。
- **KNOW_HOW**：相关的实验协议或专家经验文档。

转换后的文本字典格式类似如下：
```text
0. search_literature: Search pubmed for scientific literature...
1. analyze_protein_conservation: Align sequences to find conserved regions...
```

### 5.2 构建“评委” Prompt (LLM-as-a-Judge)
系统会拼装一段极其严格的 System Prompt，强制赋予大模型“意图分类器”的角色，并规定了基于正则表达式好提取的强格式输出。核心 Prompt 节选如下：
```text
You are an expert biomedical research assistant. Your task is to select the relevant resources to help answer a user's query.

USER QUERY: {query}
...
For each category, respond with ONLY the indices of the relevant items in the following format:
TOOLS: [list of indices]
DATA_LAKE: [list of indices]
LIBRARIES: [list of indices]
KNOW_HOW: [list of indices]
```
为了提高检索召回率（Recall），提示词中甚至硬编码了若干领域专家规则，例如：“只要是通用问题，务必包含 database tools；对于湿实验序列查询，务必包含 molecular biology tools”等。

### 5.3 独立且轻量的大模型调用
系统将上述组装好的 Prompt 加上用户的 Query，发送给大模型（默认使用 `gpt-4o` 级别的模型通过 `llm.invoke` 调用）。
**关键架构设计**：这一步调用是**完全独立于主干图网络 (LangGraph) 之外的**，且不携带繁重的历史多轮对话上下文，因此极度轻量且响应快速。大模型在此仅仅作为一个“工具分类/过滤器”使用，不负责直接回答具体的业务问题。

### 5.4 正则解析与精准按需挂载
当轻量级调用返回结果（例如文本 `TOOLS: [0, 3, 5]\nKNOW_HOW: [1]`）后：
1. **正则提取**：系统使用正则表达式（如 `re.search(r"TOOLS:\s*\[(.*?)\]", response)`）将字符串解析为 Python 整数数组 `[0, 3, 5]`。
2. **切片过滤**：根据提取出的索引，系统直接从拥有几百个对象的原始庞大资源字典中切片，精准捞出命中的那几个实体。
3. **注入上下文**：在 `biomni/agent/a1.py` 的执行入口中，系统仅将这些**少数命中的工具对象**转化为合法的 LangChain Tool Schema，并挂载到接下来的 `A1` 主智能体的上下文中。

通过这套“大模型过滤大模型”的漏斗结构（LLM Router），Biomni-Agent 既保证了工具选型的语义准确性（远优于传统的基于向量 Embeddings 的死板检索），又完美避开了全量工具挂载造成的 Context 灾难。

### 5.5 上下文消耗的量化成本分析
这套分离设计的核心价值在于**巨大的 Token 成本节约**：
1. **如果不做意图识别（全量注入）**：在 `biomni/tool/tool_description/` 目录下，包含所有 350+ 工具详细定义的 JSON Schema 字典文本体积总计约 268 KB。如果全部强塞进 LLM，仅工具定义的 System Prompt 就会消耗 **65,000 ~ 80,000 Tokens**。若带着这 8 万 Token 的拖油瓶在 LangGraph 状态机中循环 100 轮，不仅成本极为高昂，模型也会因注意力失焦而产生严重的幻觉。
2. **目前意图识别的 Prompt 大小**：`_format_resources_for_prompt` 故意丢弃了所有复杂的参数列表（Parameters），只向“裁判大模型”发送极简的一行文本（`索引号. name: description`）。这使得包含 350+ 工具、数据湖文件和经验协议的长列表被极度压缩，发送给裁判模型的单次 Prompt 大约只有 **10,000 ~ 15,000 Tokens**。

**结论**：系统仅付出 **1 次约 1.5 万 Token** 的廉价预检开销，便可精准命中 3-5 个工具。随后，主 Agent 在漫长的数十次推理死循环中，只需挂载这 3-5 个工具的 Schema（仅占用 **1000 ~ 2000 Tokens**），从而实现了极为轻巧、专注且低成本的深度任务执行。

---

## 总结
Biomni-Agent 的架构设计优先考虑了单次复杂指令的**深度执行能力**（通过 LangGraph 状态机保证长链路不断），而在**横向的多轮会话支持**上则保持了轻量级、无状态的后端设计，将跨请求的上下文维护责任交由客户端（如 Gradio 前端或业务方服务）来完成。对于长耗时任务，它也通过简单的同步超时熔断，把异步维护的复杂度交给了大模型的自行变通（如利用 Linux 后台进程）去解决。针对其海量的专属科研工具箱，系统也巧妙地利用基于 LLM 的前置检索层（Tool RAG）实现了上下文的节约与精准按需加载。
