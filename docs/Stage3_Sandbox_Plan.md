# 第三阶段：沙箱化执行环境（Sandbox Execution Engine）改造方案

在目前的 `Biomni-Agent` 中，大模型规划器（Planner）生成的 Python 代码是通过原生的 `exec()` 或 `eval()` 直接在当前宿主机环境裸跑的（例如 `biomni/tool/support_tools.py` 里的 `run_python_repl`）。
在 AIDD (AI-Driven Drug Discovery) 场景下，这会带来极高的安全风险，同时也不利于我们将计算任务横向扩展。

## 目标
将原有的危险逻辑剥离，转化为一个 **CodeExecutor 微服务**。通过 API 将代码发送至独立的 Docker 容器执行，并安全返回 stdout/stderr 和错误堆栈。

---

## 改造内容详述

### 1. 基础设施建设：构建独立的 Sandbox 容器
我们将在根目录下新建一个 `sandbox` 文件夹，并提供以下文件：

#### `[新增] sandbox/Dockerfile`
- 基础镜像采用 `mambaorg/micromamba`。
- 将我们在第一阶段抽离的 `runtime_env.yml` 拷入，并在构建时直接安装所有上百个厚重的生物信息学与数据科学依赖包。
- 暴露内部 API 端口（例如 `8081`）。

#### `[新增] sandbox/server.py`
- 这是一个非常轻量级的内部执行服务（使用 FastAPI 编写）。
- 提供一个 `POST /execute` 接口，接收一段 Python 代码作为参数。
- 内部使用 `contextlib.redirect_stdout` 捕获执行过程的输出日志，并通过 `exec()` 执行代码。因为是在 Docker 容器内，即便大模型写出破坏性代码（如 `os.system("rm -rf /")`），也不会波及宿主机。

### 2. 核心架构重构：修改 Agent 调用层

我们需要将 Agent 里面所有直接调用 `exec()` 的地方，替换为通过 HTTP RPC 调用上述 Sandbox API。

#### `[修改] biomni/tool/support_tools.py`
- 找到 `run_python_repl` 方法。
- 移除 `_persistent_namespace` 和 `exec(command, _persistent_namespace)` 的本地执行逻辑。
- 重构为：使用 `requests.post("http://localhost:8081/execute", json={"code": command})`。
- 接管返回的 json 数据，解析出 `stdout`, `stderr` 或者报错栈，原样返回给 Agent 规划器。

#### `[修改] biomni/tool/lab_automation.py`
- 该文件中针对 PyLabRobot 验证的 `_run_script_with_monitoring` 同样包含了 `exec()`，也将其路由至 Sandbox 执行。

---

## 需要你决定的开放性问题 (Open Questions)

在实际编写代码前，由于沙箱涉及到安全边界，我有两个细节需要向你确认：

1. **数据文件的挂载（Data Volumes）**：
   Agent 在写代码时通常需要读取和保存文件。我们是否需要将宿主机上的 `./data` 目录直接挂载（mount）到 Docker 沙箱中？
   *(建议：挂载 `./data` 目录，这样 Agent 依然可以分析本地数据集，画图并保存到该目录中)*

2. **网络隔离（Network Isolation）**：
   在真正的高安全环境中，我们通常会切断沙箱容器的外网访问，以防大模型编写的恶意代码进行数据外传。我们目前的改造需要彻底切断沙箱的公网访问吗？还是为了下载一些生信工具数据库，暂且保留其联网能力？

---

## 后续验证流程
当你批准本方案并回答上述问题后，我会：
1. 为你生成 `sandbox/Dockerfile` 和 `sandbox/server.py`。
2. 为你修改相应的 `support_tools.py` 等源码。
3. 提供一行简单的 `docker run` 命令让你在后台启动这个沙箱。
4. 在网关中调用一次请求进行端到端测试。

**请阅读本文件，并告诉我你的选择！**
