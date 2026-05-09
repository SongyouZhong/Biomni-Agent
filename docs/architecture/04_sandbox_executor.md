# Sandbox Executor (沙箱执行引擎) 架构设计

在旧架构中，所有由大模型编写的 Python 脚本或计算任务均在宿主机上通过 `exec()` 直接执行，这存在任意代码执行（RCE）的风险，并且容易污染核心服务环境。
重构后的 Sandbox Executor 是一个独立的、加固的微服务。

## 1. 核心职责
- **环境隔离**：所有不受信任的代码均在单独的 Docker 容器中执行，进程被严格限制在容器内部。
- **环境预置**：预先编译和安装了复杂的生物信息学库（如 `macs2`, `pybedtools` 等 C-extensions）和 AIDD 相关依赖，避免运行时安装开销。
- **执行与拦截**：
  - **流拦截**：动态重定向 `sys.stdout` 和 `sys.stderr` 捕获脚本输出。
  - **图形拦截**：Monkey-patch `matplotlib.pyplot.show()`，拦截大模型绘制的图表，直接转换为 Base64 图片返回，免去了文件系统落地读取的麻烦。

## 2. 内部工作流程图

```mermaid
sequenceDiagram
    participant Agent as A1 Agent
    participant RPC as HTTP Server (server.py)
    participant ExecEngine as Exec() Engine
    participant Output as IO/Plot Capture

    Agent->>RPC: POST /execute {"code": "print('Hello'); plt.plot()"}
    
    activate RPC
    RPC->>Output: 1. Setup Redirects (stdout/stderr)
    RPC->>Output: 2. Monkey-patch Matplotlib
    RPC->>ExecEngine: 3. exec(code, namespace)
    
    activate ExecEngine
    Note over ExecEngine: 执行复杂的生物或科学计算
    ExecEngine-->>Output: 产生文本日志与图表对象
    deactivate ExecEngine
    
    Output-->>RPC: 返回拦截到的文字与 Base64 图片
    RPC-->>Agent: HTTP 200 JSON {stdout, stderr, images}
    deactivate RPC
```

## 3. 安全与扩展性设计
- **体积挂载**：仅通过 `-v ./data:/data` 共享必要的数据湖目录，保护宿主机其余文件系统。
- **无状态设计**：每次 HTTP 请求都在全局命名空间（预初始化的字典）中执行，保障连续对话上下文的延续，但随时可以重启容器获得干净环境。
