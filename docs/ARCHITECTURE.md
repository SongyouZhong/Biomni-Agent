# Biomni 项目架构说明

## 一、项目定位

Biomni 是一个**通用生物医学 AI Agent 框架**，将大型语言模型（LLM）的推理能力与代码执行环境、领域工具库、生物数据湖和知识文档结合，使 AI 能自主规划并执行跨生物医学子领域（基因组学、药理学、细胞生物学等 20+ 个领域）的研究任务。

---

## 二、目录结构

```
Biomni-Agent/
├── biomni/                     # 核心包
│   ├── config.py               # 全局配置管理
│   ├── llm.py                  # LLM 多后端工厂
│   ├── utils.py                # 通用工具函数
│   ├── env_desc.py             # 学术模式：数据集/库描述字典
│   ├── env_desc_cm.py          # 商业模式：数据集/库描述字典
│   ├── version.py
│   ├── agent/                  # Agent 核心逻辑
│   │   ├── a1.py               # 主 Agent（A1 类，基于 LangGraph）
│   │   ├── react.py            # ReAct Agent（LangChain 工具调用模式）
│   │   ├── function_generator.py # 代码生成 Agent
│   │   ├── env_collection.py   # 论文任务提取 Agent
│   │   └── qa_llm.py           # 问答 Agent
│   ├── tool/                   # 工具层（22 个生物医学领域模块）
│   │   ├── tool_registry.py    # 工具注册与索引
│   │   ├── support_tools.py    # 代码执行 REPL（Python/R/Bash）
│   │   ├── genomics.py         # 基因组学工具
│   │   ├── molecular_biology.py
│   │   ├── pharmacology.py
│   │   ├── ... (共 22 个)
│   │   ├── tool_description/   # 各模块 API Schema 描述文件
│   │   ├── schema_db/          # Schema 数据库
│   │   ├── protocols/          # 本地实验流程数据
│   │   └── example_mcp_tools/  # MCP 工具示例
│   ├── model/
│   │   └── retriever.py        # 基于 LLM Prompt 的资源检索器
│   ├── know_how/               # 领域知识文档系统
│   │   ├── loader.py           # Markdown 文档加载器
│   │   ├── sgRNA_design_guide.md
│   │   ├── single_cell_annotation.md
│   │   └── resource/           # 参考资源文件
│   ├── task/                   # 任务评测接口
│   │   ├── base_task.py
│   │   ├── hle.py
│   │   └── lab_bench.py
│   ├── eval/                   # 评测系统
│   │   └── biomni_eval1.py
│   └── biorxiv_scripts/        # bioRxiv 任务提取脚本
├── biomni_env/                 # 环境配置
│   ├── setup.sh                # 一键环境安装脚本
│   ├── bio_env.yml             # Conda 环境定义
│   ├── install_cli_tools.sh    # CLI 工具安装
│   └── install_r_packages.R    # R 包安装
├── tutorials/                  # 使用教程
│   ├── biomni_101.ipynb
│   └── examples/               # 各场景示例（克隆、pylabrobot、MCP 等）
└── docs/                       # 文档
```

---

## 三、整体架构（逻辑分层）

```
┌─────────────────────────────────────────────────────────────┐
│                       用户接口层                             │
│         A1.go()  /  A1.go_stream()  /  A1.go_interactive()  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    核心 Agent 层（agent/）                    │
│                                                             │
│   A1（主 Agent）                                            │
│   ┌────────────────────────────────────────────┐           │
│   │           LangGraph 状态机                  │           │
│   │  START → generate ⇌ execute → END           │           │
│   │          ↕ self_critic（可选）               │           │
│   └────────────────────────────────────────────┘           │
│                                                             │
│   react（备用 ReAct Agent）  │  FunctionGenerator           │
└──────┬───────────────────────┬──────────────────────────────┘
       │                       │
┌──────▼──────┐   ┌────────────▼────────────────────────────┐
│   LLM 层    │   │           资源检索层                     │
│  llm.py     │   │  ToolRetriever   KnowHowLoader           │
│             │   │  ToolRegistry    （prompt-based 检索）    │
│  8 种后端   │   └────────────────────────────────────────┘
└──────┬──────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                    工具执行层（tool/）                        │
│                                                             │
│  22 个领域工具模块（Python 函数）                            │
│  support_tools.py（持久化 Python REPL + R + Bash）          │
│  tool_description/（API Schema JSON）                       │
│  MCP 集成（双向 MCP 协议支持）                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      数据资源层                               │
│                                                             │
│  生物数据湖（biomni_data/data_lake/，S3 自动下载）            │
│  env_desc.py / env_desc_cm.py（100+ 数据集描述字典）          │
│  know_how/（领域知识 Markdown 全文嵌入系统提示词）            │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、核心模块详解

### 4.1 配置系统 — `config.py`

`BiomniConfig` 是一个 Python `dataclass`，集中管理所有可配置项。

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `path` | `./data` | 数据存储路径 |
| `llm` | `claude-sonnet-4-5` | 默认 LLM 模型名 |
| `source` | 自动推断 | LLM 提供商 |
| `use_tool_retriever` | `True` | 是否启用动态工具检索 |
| `timeout_seconds` | `600` | 代码执行超时（秒）|
| `temperature` | `0.7` | 生成温度 |
| `commercial_mode` | `False` | 商业/学术数据集切换 |
| `base_url` | `None` | 自定义模型服务地址 |

**配置优先级**：构造函数参数 > 环境变量（`BIOMNI_*`）> 数据类默认值。

---

### 4.2 LLM 抽象层 — `llm.py`

`get_llm()` 是统一的 LLM 工厂函数，通过模型名称前缀**自动推断**后端提供商：

| Source | 模型前缀/特征 | LangChain 类 |
|---|---|---|
| `Anthropic` | `claude-` | `ChatAnthropic` |
| `OpenAI` | `gpt-` | `ChatOpenAI` |
| `AzureOpenAI` | `azure-` | `AzureChatOpenAI` |
| `Gemini` | `gemini-` | `ChatGoogleGenerativeAI` |
| `Groq` | 含 `groq` | `ChatGroq` |
| `Bedrock` | `anthropic.claude-` 等 | `ChatBedrock` |
| `Ollama` | `llama`、`mistral` 等 | `ChatOllama` |
| `Custom` | 指定 `base_url` | `ChatOpenAI`（自定义端点）|

API Key 通过环境变量注入（`.env` 文件），不存储于配置对象中。

---

### 4.3 主 Agent — `agent/a1.py`

`A1` 是系统核心，基于 **LangGraph** 实现了一个带状态持久化的 **ReAct 循环**。

#### Agent 状态
```python
class AgentState(TypedDict):
    messages: list[BaseMessage]   # 完整对话历史
    next_step: str | None         # "generate" | "execute" | "end"
```

#### 工作流状态机

```
          ┌─────────────────────────┐
          │          START          │
          └────────────┬────────────┘
                       ▼
          ┌─────────────────────────┐
     ┌───►│        generate         │◄──────────────────┐
     │    │  LLM 推理 + 标签解析     │                   │
     │    └──────┬──────────┬───────┘                   │
     │           │          │                           │
     │      <execute>   <solution>                      │
     │           │          │                           │
     │    ┌──────▼──────┐  END              ┌──────────────────┐
     │    │   execute   │          ┌────────► self_critic       │
     │    │ Python/R/Bash│         │        │ LLM 自我评价      │
     │    └──────┬──────┘         │        └──────────────────┘
     │           │                │（test_time_scale 模式下启用）
     └───────────┘    <solution>──┘
       <observation>
```

#### generate 节点流程
1. 组装 `[SystemMessage] + messages` 发送给 LLM
2. 处理响应内容中的列表块（兼容 Anthropic Responses API）
3. 修复不完整的 XML 标签（`</execute>` 缺失时自动补全）
4. 正则匹配 `<execute>`、`<solution>`、`<think>` 标签决定下一步
5. 连续解析失败超过 2 次时强制终止

#### execute 节点流程
根据代码块开头标记分发到三个执行器：
- `#!R` → `run_r_code()`，写临时文件调用 `Rscript`
- `#!BASH` / `#!CLI` → `run_bash_script()`，`subprocess` 执行
- 默认 → `run_python_repl()`，在共享 `_persistent_namespace` 中执行

所有执行均受 `timeout_seconds` 超时保护，输出超过 10,000 字符时自动截断。

---

### 4.4 代码执行环境 — `tool/support_tools.py`

```python
_persistent_namespace = {}   # 跨多轮执行共享的 Python 命名空间
```

- 变量在多轮 `<execute>` 间持久存在（类似 Jupyter Kernel）
- 自定义函数通过 `builtins._biomni_custom_functions` 注入命名空间
- 内置 Matplotlib 图表捕获机制（Base64 编码存储）

---

### 4.5 系统提示词生成 — `_generate_system_prompt()`

动态构造 LLM 的系统提示词，包含以下区块（按优先级顺序）：

```
┌──────────────────────────────────────────────────────────┐
│ 1. 角色定义与规划格式（ReAct + 进度 Checklist 规范）       │
├──────────────────────────────────────────────────────────┤
│ 2. 执行规范（<execute>/<solution> 标签用法，三种语言标记） │
├──────────────────────────────────────────────────────────┤
│ 3. PRIORITY 区块（仅用户有自定义资源时显示）               │
│    📚 Know-How 文档全文                                   │
│    🔧 自定义工具列表                                      │
│    📊 自定义数据集列表                                    │
│    ⚙️  自定义软件列表                                     │
├──────────────────────────────────────────────────────────┤
│ 4. 工具字典（module → API 函数列表）                      │
├──────────────────────────────────────────────────────────┤
│ 5. 生物数据湖清单（文件名 + 描述）                         │
├──────────────────────────────────────────────────────────┤
│ 6. 软件库清单（Python/R/CLI 包 + 描述）                   │
└──────────────────────────────────────────────────────────┘
```

**两种模式**：
- `is_retrieval=False`：全量工具列表，用于初始配置
- `is_retrieval=True`：经检索器筛选的子集，用于具体任务执行

---

### 4.6 资源检索系统 — `model/retriever.py`

`ToolRetriever.prompt_based_retrieval()` 在执行每个任务前动态筛选上下文资源。

**检索流程：**

```
用户查询
    │
    ▼
构造资源目录提示词
（所有工具名+描述 / 数据集名+描述 / 库名+描述 / Know-How 摘要）
    │
    ▼
LLM 输出各类别的相关索引列表
（内置偏好规则：数据库工具、文献工具、分子生物学工具优先入选）
    │
    ▼
提取对应资源全量信息
    │
    ▼
重新生成系统提示词（仅含筛选后资源）
```

---

### 4.7 工具注册系统 — `tool/tool_registry.py`

每个工具以如下 JSON Schema 注册：

```json
{
  "id": 42,
  "name": "annotate_celltype_scRNA",
  "description": "基于基因标记和参考数据集注释单细胞 RNA 细胞类型",
  "required_parameters": [
    {"name": "adata_filename", "type": "str", "description": "..."}
  ],
  "optional_parameters": [
    {"name": "llm", "type": "str", "default": "claude-3-5-sonnet-20241022"}
  ],
  "module": "biomni.tool.genomics"
}
```

工具加载路径：`tool_description/*.py` → `read_module2api()` → `module2api` 字典 → `ToolRegistry`。

---

### 4.8 知识文档系统 — `know_how/`

`KnowHowLoader` 从包目录扫描所有 `.md` 文件，解析 `## Metadata` 段落中的结构化元数据：

| 元数据字段 | 用途 |
|---|---|
| `short_description` | 检索摘要 |
| `commercial_use` | 商业模式过滤依据 |

知识文档**全文嵌入**初始系统提示词（`configure()` 阶段），Agent 无需额外检索即可直接引用。

---

### 4.9 数据湖 — `env_desc.py`

维护 100+ 个生物数据集的描述字典，覆盖：

| 数据类别 | 示例数据集 |
|---|---|
| 基因组学 | GWAS Catalog、GTEx、GeneBass |
| 癌症生物学 | DepMap CRISPRGeneEffect、OmicsExpression |
| 药物发现 | BindingDB、Broad Repurposing Hub、DDInter |
| 单细胞 | CZI Census、marker_celltype |
| 蛋白互作 | affinity_capture-ms、co-fractionation |
| 基因本体 | GO、HPO、MSigDB、MouseMine |
| miRNA | miRDB、miRTarBase |
| 知识图谱 | Precision Medicine KG（1.7 万种疾病，400 万关系）|

数据文件初始化时自动从 S3（`biomni-release.s3.amazonaws.com`）下载缺失文件。

---

### 4.10 MCP 集成 — `A1.add_mcp()`

Biomni 支持双向 Model Context Protocol（MCP）集成：

#### 外部 MCP Server → Biomni（导入工具）

```
YAML 配置文件
    │
    ├─ 支持启动方式：Docker / NPM / Python 模块 / 可执行文件
    │
    ├─ 自动发现：连接 MCP Server，调用 list_tools()
    │  或 手动定义：在 YAML 中描述 tools 列表
    │
    ├─ 为每个工具创建 sync_tool_wrapper()（屏蔽 asyncio 复杂性）
    │
    └─ 注册到 ToolRegistry + module2api（立即可用）
```

#### Biomni → 外部（暴露为 MCP Server）

参见 `tutorials/examples/expose_biomni_server/`。

---

### 4.11 动态扩展 API

`A1` 类提供完整的运行时扩展接口：

| 方法 | 功能 |
|---|---|
| `add_tool(fn)` | 传入 Python 函数，LLM 自动生成 Schema 并注册 |
| `add_data(dict)` | 向数据湖注册自定义数据集（文件名 → 描述）|
| `add_software(dict)` | 向软件库添加自定义包描述 |
| `add_mcp(config_path)` | 从 YAML 批量注册 MCP 工具 |
| `remove_custom_tool(name)` | 移除已注册自定义工具 |
| `list_custom_tools()` | 列出所有自定义工具 |

每次变更后自动调用 `configure()` 重新生成系统提示词。

---

### 4.12 评测系统 — `eval/biomni_eval1.py`

`BiomniEval1` 从 HuggingFace（`biomni/Eval1`）加载 Parquet 格式基准数据集，按 `task_name` 分发任务特定评分逻辑：

| 任务类型 | 评分方式 |
|---|---|
| `crispr_delivery` | 精确匹配（字母选项）|
| `gwas_causal_gene_*` | 基因名大写精确匹配 |
| 其他 | 任务特定逻辑 |

---

## 五、完整执行流程

```
用户：A1.go("分析 TP53 在癌症中的基因依赖性")
        │
        ▼
① 资源检索（use_tool_retriever=True 时）
   ToolRetriever.prompt_based_retrieval()
   → LLM 从 100+ 工具、数据集、库中选择相关子集
   → 重新生成精简系统提示词
        │
        ▼
② LangGraph 状态机启动（config: thread_id=42, recursion_limit=500）
        │
        ▼
③ generate() — LLM 生成响应
   输入：[SystemMessage(system_prompt)] + [HumanMessage(任务)]
   输出：思考过程 + <execute> 代码块
        │
        ▼
④ execute() — 代码执行
   解析代码类型（Python 默认）
   run_python_repl() 在持久命名空间中执行
   结果包装为 <observation>...</observation>
        │
        ▼
⑤ 循环 ③-④（多轮工具调用）
        │
        ▼
⑥ generate() 输出 <solution>答案</solution>
        │
        ▼
⑦ 返回 (log, final_answer)
   log 包含所有对话轮次的格式化输出
```

---

## 六、工具领域覆盖（22 个模块）

| 模块 | 代表功能 |
|---|---|
| `genomics` | 单细胞 RNA 分析、细胞类型注释、ESM 蛋白嵌入 |
| `genetics` | GWAS 分析、基因变异注释 |
| `molecular_biology` | 克隆设计、PCR、限制性酶切分析 |
| `cancer_biology` | DepMap 依赖性分析、CRISPR 筛选解读 |
| `pharmacology` | 药物相互作用、药物重利用预测 |
| `immunology` | TCR/BCR 序列分析 |
| `cell_biology` | 细胞培养、流式细胞分析 |
| `synthetic_biology` | 基因线路设计、元件检索 |
| `bioimaging` | 图像分析、显微镜数据处理 |
| `biophysics` | 分子动力学、结构分析 |
| `biochemistry` | 代谢分析、酶动力学 |
| `bioengineering` | 生物反应器、发酵工艺 |
| `glycoengineering` | 糖工程、聚糖分析 |
| `systems_biology` | 通路富集、网络分析 |
| `microbiology` | 微生物鉴定、宏基因组 |
| `pathology` | 病理图像分析 |
| `physiology` | 生理学数据分析 |
| `lab_automation` | PyLabRobot 液体处理自动化 |
| `literature` | PubMed 检索、全文解析 |
| `database` | 多生物数据库统一查询接口 |
| `protocols` | 实验流程搜索与解析 |
| `support_tools` | 代码 REPL 执行基础设施 |

---

## 七、技术栈

| 层次 | 技术选型 |
|---|---|
| Agent 框架 | LangGraph（有向图状态机 + 检查点持久化）|
| LLM 接入 | LangChain（统一多后端接口）|
| 默认 LLM | Claude Sonnet 系列（Anthropic）|
| 代码执行 | 自研持久化 Python REPL + Rscript + subprocess Bash |
| MCP | `mcp` Python SDK + `nest_asyncio` |
| 数据处理 | Pandas、PyArrow（Parquet）|
| 生物工具 | scanpy、gget、esm、pybiomart、gseapy、popv 等 |
| 配置管理 | Python `dataclass` + python-dotenv + 环境变量 |
| 打包发布 | pyproject.toml（PEP 517/518）+ PyPI |
| 环境管理 | Conda（`biomni_e1` 环境）|

---

## 八、关键设计决策

### 8.1 代码即动作（Code-as-Action）
LLM 不直接调用预定义工具函数，而是**生成完整的 Python/R/Bash 代码**通过 REPL 执行。这带来极大的灵活性——Agent 可以组合任意工具、编写数据处理逻辑、调用外部 CLI，而无需为每种组合预先定义接口。

### 8.2 两级上下文策略
- **初始化阶段**：将全量工具描述、Know-How 文档嵌入系统提示词（全局可见）
- **任务执行阶段**（`use_tool_retriever=True`）：用 LLM 从全量资源中筛选相关子集，替换系统提示词，避免上下文过长导致注意力分散

### 8.3 持久化执行命名空间
Python REPL 使用全局 `_persistent_namespace` 字典，变量在多轮 `<execute>` 间持久存在，行为类似 Jupyter Notebook Kernel，允许 Agent 分步执行复杂分析任务。

### 8.4 商业/学术双模式
通过 `commercial_mode` 标志在两套数据集描述字典（`env_desc.py` / `env_desc_cm.py`）和 Know-How 文档间切换，确保数据许可证合规。

### 8.5 运行时热插拔
用户可在 Agent 运行中随时通过 `add_tool()` / `add_data()` / `add_mcp()` 注入新能力，每次变更后自动重新构建系统提示词，无需重启 Agent。

### 8.6 自我评价（Test-Time Scaling）
`configure(self_critic=True, test_time_scale_round=N)` 模式下，Agent 在给出答案前会额外调用 `test_time_scale_round` 次自我评价循环——LLM 对已有推理和执行结果进行批评，并据此修正，以牺牲推理时长换取更高准确率。
