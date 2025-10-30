# MCP Manager 使用说明

## 架构概览

```
MCPManager (全局单例)
  ↓
读取 mcp_config.json 配置文件
  ↓
连接所有启用的 MCP Server
  ↓
获取所有工具并转换为 LangChain Tool
  ↓
提供给 General Agent 使用
```

## 文件结构

```
backend/app/mcp/
├── __init__.py         # 模块入口，导出 mcp_manager
├── client.py           # 通用 MCP Client（可连接任何 MCP Server）
├── manager.py          # MCP Manager（管理多个 Server，动态加载工具）
├── config.py           # 配置加载器（从 JSON 读取）
├── mcp_config.json     # MCP Servers 配置文件（JSON 格式）★
└── README.md           # 使用文档
```

## 快速开始

### 1. 安装依赖

```bash
# 安装 MCP Python SDK
pip install mcp

# 安装 DuckDuckGo MCP Server
npm install -g duckduckgo-mcp-server

# 或者使用 npx（不需要全局安装）
npx -y duckduckgo-mcp-server
```

### 2. 配置 MCP Server

编辑 `backend/app/mcp/mcp_config.json`：

```json
{
  "mcpServers": {
    "duckduckgo-search": {
      "command": "npx",
      "args": ["-y", "duckduckgo-mcp-server"],
      "description": "DuckDuckGo 搜索",
      "enabled": true
    }
  }
}
```

### 3. 运行测试

```bash
cd backend
uvicorn app.main:app --reload
```

测试对话：
- "特朗普最新新闻"
- "Python 3.13 有什么新特性？"
- "2024年AI领域有哪些突破？"

## 配置文件说明

### 标准格式（与 Claude Desktop 一致）

```json
{
  "mcpServers": {
    "server-name": {
      "command": "启动命令",
      "args": ["参数1", "参数2"],
      "env": {
        "ENV_VAR": "${ENV_VAR_NAME}"
      },
      "description": "描述信息",
      "enabled": true
    }
  }
}
```

### 字段说明

- **command**: 启动命令（如 `npx`, `python`, `uv`, `node`）
- **args**: 命令参数数组
- **env**: 环境变量（可选）
  - 使用 `${VAR_NAME}` 格式引用系统环境变量
- **description**: 服务器描述（可选）
- **enabled**: 是否启用（默认 `true`）

### 环境变量占位符

配置文件中可以使用 `${VAR_NAME}` 引用环境变量：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

系统会自动从 `.env` 文件或系统环境变量中读取 `GITHUB_TOKEN`。

## 配置示例

### 示例 1: DuckDuckGo 搜索（无需 API Key）

```json
{
  "mcpServers": {
    "duckduckgo-search": {
      "command": "npx",
      "args": ["-y", "duckduckgo-mcp-server"],
      "description": "DuckDuckGo 网页搜索",
      "enabled": true
    }
  }
}
```

### 示例 2: Playwright 浏览器自动化

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"],
      "description": "Playwright 浏览器自动化",
      "enabled": true
    }
  }
}
```

### 示例 3: 自定义 Python MCP Server

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": [
        "--directory",
        "E:\\ClaudeTool\\weather",
        "run",
        "weather.py"
      ],
      "description": "天气查询服务",
      "enabled": true
    }
  }
}
```

### 示例 4: 直接运行 Python 脚本

```json
{
  "mcpServers": {
    "android_adb": {
      "command": "D:\\Projects\\adb_mcp_server\\Scripts\\python.exe",
      "args": [
        "E:\\ClaudeTool\\adb_mcp_server\\src\\adb_server.py"
      ],
      "description": "Android ADB 控制",
      "enabled": true
    }
  }
}
```

### 示例 5: 文件系统操作

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/path/to/allowed/directory"
      ],
      "description": "文件系统操作",
      "enabled": true
    }
  }
}
```

### 示例 6: GitHub 操作（需要 Token）

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      },
      "description": "GitHub 仓库操作",
      "enabled": true
    }
  }
}
```

记得在 `.env` 文件中设置：
```bash
GITHUB_TOKEN=your_github_token_here
```

## 添加新的 MCP Server

### 方式 1: 编辑 JSON 配置文件（推荐）

直接编辑 `mcp_config.json`：

```json
{
  "mcpServers": {
    "existing-server": { ... },

    "new-server": {
      "command": "npx",
      "args": ["-y", "new-mcp-server"],
      "description": "新的 MCP Server",
      "enabled": true
    }
  }
}
```

### 方式 2: 代码中动态注册

```python
from app.mcp import mcp_manager

# 动态注册新的 MCP Server
mcp_manager.register_server(
    name="my-custom-server",
    command="npx",
    args=["-y", "my-mcp-server"],
    env={"API_KEY": "xxx"},
    description="自定义 MCP Server",
    enabled=True
)
```

### 方式 3: 使用配置加载器保存

```python
from app.mcp.config import load_mcp_config, save_mcp_config

# 加载现有配置
servers = load_mcp_config()

# 添加新 Server
servers["new-server"] = {
    "command": "npx",
    "args": ["-y", "new-mcp-server"],
    "description": "新的 MCP Server",
    "enabled": True
}

# 保存配置
save_mcp_config(servers)
```

## 启用/禁用 Server

只需修改 `enabled` 字段：

```json
{
  "mcpServers": {
    "duckduckgo-search": {
      "command": "npx",
      "args": ["-y", "duckduckgo-mcp-server"],
      "enabled": false   // 禁用
    }
  }
}
```

## 工作流程

### General Agent 如何使用 MCP 工具

1. **启动时**:
   - 读取 `mcp_config.json`
   - 解析配置并替换环境变量
   - 筛选出 `enabled: true` 的 Server

2. **用户发送消息** → Supervisor 路由到 General Agent

3. **General Agent 启动**:
   - 调用 `mcp_manager.load_all_tools()` 加载所有 MCP 工具
   - 连接所有启用的 MCP Server
   - 获取工具列表并转换为 LangChain Tool
   - 将工具传递给 LLM（Function Calling）

4. **LLM 决策**:
   - 分析用户问题
   - 决定是否需要调用工具
   - 返回要调用的工具名和参数

5. **执行工具**:
   - MCP Manager 连接对应的 MCP Server
   - 调用工具
   - 返回结果

6. **生成回答**:
   - LLM 基于工具结果生成最终回答
   - 返回给用户

## 可用的 MCP Servers

### 官方 MCP Servers

1. **@modelcontextprotocol/server-filesystem** - 文件系统操作
2. **@modelcontextprotocol/server-github** - GitHub 操作
3. **@modelcontextprotocol/server-postgres** - PostgreSQL 数据库
4. **@modelcontextprotocol/server-brave-search** - Brave Search（需要 API Key）
5. **@modelcontextprotocol/server-fetch** - 网页抓取
6. **@playwright/mcp** - Playwright 浏览器自动化

### 社区 MCP Servers

1. **duckduckgo-mcp-server** - DuckDuckGo 搜索（无需 API Key）
2. 更多: https://github.com/modelcontextprotocol/servers

## 故障排除

### 问题 1: 配置文件格式错误

**现象**:
```
[MCP Config] 错误: JSON 格式错误: ...
```

**解决**:
- 检查 JSON 语法（逗号、引号、括号）
- 使用 JSON 验证工具: https://jsonlint.com/
- 确保没有多余的逗号

### 问题 2: 环境变量未设置

**现象**:
```
[MCP Config] 警告: 环境变量 GITHUB_TOKEN 未设置
```

**解决**:
- 在 `.env` 文件中添加环境变量
- 或在系统环境变量中设置
- 检查环境变量名称拼写

### 问题 3: MCP Server 启动失败

**现象**:
```
[MCP Client] 连接失败: ...
```

**解决**:
- 检查 MCP Server 是否已安装
- 检查命令路径是否正确
- 检查 Node.js/Python 版本
- 查看详细错误日志

### 问题 4: 工具未加载

**现象**:
```
[General Agent] MCP 工具加载完成，共 0 个工具
```

**解决**:
- 检查 `enabled: true`
- 检查 JSON 格式是否正确
- 手动测试 MCP Server 是否正常

## 高级用法

### 同时使用多个 MCP Server

```json
{
  "mcpServers": {
    "duckduckgo-search": {
      "command": "npx",
      "args": ["-y", "duckduckgo-mcp-server"],
      "enabled": true
    },
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"],
      "enabled": true
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
      "enabled": true
    }
  }
}
```

所有工具会自动合并提供给 Agent。

### 测试 MCP 配置

创建测试脚本 `test_mcp.py`：

```python
from app.mcp.config import load_mcp_config, get_enabled_servers

# 测试加载配置
print("所有 Server:")
all_servers = load_mcp_config()
for name, config in all_servers.items():
    print(f"  {name}: {config}")

print("\n启用的 Server:")
enabled = get_enabled_servers()
for name, config in enabled.items():
    print(f"  {name}: {config.get('description')}")
```

## 性能优化

### 优化 1: 缓存工具加载

当前每次调用 General Agent 都会重新加载工具，可以改为：

```python
# 在模块级别缓存
_cached_tools = None

def create_general_agent():
    global _cached_tools
    if _cached_tools is None:
        _cached_tools = mcp_manager.load_all_tools()
    # ...
```

### 优化 2: 并行加载多个 Server

修改 `manager.py` 的 `load_all_tools_async()` 使用 `asyncio.gather()` 并行加载。

## 从 Claude Desktop 迁移配置

如果你有 Claude Desktop 的配置，可以直接复制 `mcpServers` 部分：

**Claude Desktop 配置位置**:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

**复制配置**:
```json
// 从 Claude Desktop 配置
{
  "mcpServers": {
    "your-server": { ... }
  }
}

// 粘贴到 mcp_config.json
{
  "mcpServers": {
    "your-server": { ... }
  }
}
```

添加 `enabled` 字段即可。

## 下一步

1. 测试 DuckDuckGo 搜索功能
2. 添加更多 MCP Server（Playwright、文件系统等）
3. 优化工具加载性能
4. 添加工具调用日志和监控
