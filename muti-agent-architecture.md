，# 导航多智能体系统 - 完整技术架构文档

> 项目目标: 基于 LangGraph 构建 Supervisor 模式的 Multi-Agent 系统,通过 Web 界面与智能体对话,实现导航控制和信息查询功能。

---

## 📋 目录

- [1. 项目概述](#1-项目概述)
- [2. 系统架构](#2-系统架构)
- [3. 技术选型](#3-技术选型)
- [4. 核心模块设计](#4-核心模块设计)
- [5. 项目结构](#5-项目结构)
- [6. 实现路线图](#6-实现路线图)
- [7. 测试场景](#7-测试场景)
- [8. 部署方案](#8-部署方案)

---

## 1. 项目概述

### 1.1 功能目标

**核心功能**:
- 用户通过 Web 前端与 Multi-Agent 系统对话
- **导航功能**: 用户说"导航到XXX",Agent 调用 MCP Tool 控制 Android 模拟器上的导航应用开始导航
- **天气查询**: 用户询问"某地天气",Agent 调用天气 API 返回天气信息

**技术目标**:
- 深入学习 LangGraph 框架
- 掌握 Supervisor 模式的 Multi-Agent 架构
- 实现流式对话 UI
- 集成现有的 Java MCP Server (导航部分)

### 1.2 系统特点

- ✅ **前后端分离**: React + FastAPI
- ✅ **流式响应**: SSE 实时推送
- ✅ **状态持久化**: SQLite Checkpointing
- ✅ **可扩展**: 易于添加新 Agent
- ✅ **真实场景**: 实际控制导航应用

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                   Web 前端 (React)                       │
│   • Chat UI 界面                                         │
│   • useStream Hook (流式响应处理)                       │
│   • 实时显示 Agent 执行过程                              │
└──────────────────┬──────────────────────────────────────┘
                   │ SSE (Server-Sent Events)
                   ↓
┌─────────────────────────────────────────────────────────┐
│              后端 API 层 (FastAPI)                       │
│   • /api/chat/stream - SSE 流式接口                      │
│   • /api/chat - 标准接口 (测试用)                        │
│   • /api/health - 健康检查                               │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│         LangGraph Multi-Agent 系统                       │
│                                                          │
│   ┌──────────────────────────────────────┐             │
│   │      Supervisor Agent                │             │
│   │   • 任务分析                          │             │
│   │   • Agent 调度                        │             │
│   │   • 结果汇总                          │             │
│   └──────────────┬───────────────────────┘             │
│                  │                                       │
│         ┌────────┴────────┐                             │
│         ↓                 ↓                             │
│   ┌──────────┐      ┌──────────┐                       │
│   │Navigation│      │ Weather  │                       │
│   │  Agent   │      │  Agent   │                       │
│   │          │      │          │                       │
│   │ 导航专家  │      │ 天气查询  │                       │
│   └────┬─────┘      └────┬─────┘                       │
│        │                 │                              │
└────────┼─────────────────┼──────────────────────────────┘
         │                 │
         ↓                 ↓
┌──────────────────┐  ┌──────────────────┐
│  MCP Tools       │  │  Weather API     │
│                  │  │                  │
│ • plan_route     │  │ • 直接调用       │
│ • start_nav      │  │   公开天气API    │
└────────┬─────────┘  │ • 无需MCP Server │
         │            └──────────────────┘
         ↓
┌──────────────────┐
│ Java MCP Server  │
│  (你现有的)       │
│                  │
│ • 接收HTTP请求   │
│ • 调用导航应用   │
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│ Android 模拟器   │
│  (导航应用)      │
└──────────────────┘
```

### 2.2 Multi-Agent 架构模式

**选择: Supervisor 模式**

```
用户输入: "导航到机场,查一下那边天气"
    ↓
┌─────────────────────────────────────┐
│  Supervisor Agent                   │
│  1. 分析用户意图                     │
│  2. 识别需要的 Agent                 │
│  3. 决定执行顺序                     │
└─────────────┬───────────────────────┘
              │
         分解为2个任务
              │
    ┌─────────┴─────────┐
    ↓                   ↓
┌─────────┐        ┌─────────┐
│Navigation│        │ Weather │
│ Agent   │        │ Agent   │
└────┬────┘        └────┬────┘
     │                  │
     └─────────┬────────┘
               ↓
        回到 Supervisor
               ↓
          汇总结果返回
```

**为什么选 Supervisor?**
- ✅ 中心化控制,流程清晰
- ✅ 适合车载场景(安全可控)
- ✅ 调试友好
- ✅ LangGraph 官方主推,文档丰富

---

## 3. 技术选型

### 3.1 后端技术栈

| 组件 | 技术 | 版本 | 理由 |
|------|------|------|------|
| Web 框架 | **FastAPI** | 0.109+ | • 异步支持<br>• 内置 WebSocket/SSE<br>• 自动文档<br>• 高性能 |
| Agent 引擎 | **LangGraph** | 0.0.20+ | • Supervisor 模式<br>• 状态管理<br>• 生产级成熟度 |
| LLM | **OpenAI GPT-4** / DeepSeek | - | 按需选择 |
| 数据库 | **SQLite** (开发)<br>PostgreSQL (生产) | - | • LangGraph checkpointing<br>• 对话历史存储 |
| 通信协议 | **SSE** | - | • 单向流式<br>• 实现简单<br>• 自动重连 |

**核心依赖**:
```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
langchain==0.1.0
langchain-openai==0.0.5
langgraph==0.0.20
langchain-core==0.1.0
requests==2.31.0
python-dotenv==1.0.0
aiosqlite==0.19.0
```

### 3.2 前端技术栈

| 组件 | 技术 | 理由 |
|------|------|------|
| 框架 | **React** | • 生态丰富<br>• 组件化开发 |
| 语言 | **TypeScript** | • 类型安全 |
| UI | 自定义 Chat 组件 | • 轻量灵活 |
| 状态管理 | **React Hooks** | • useLangGraphStream (自定义) |
| 样式 | **Tailwind CSS** | 快速开发 |
| 构建工具 | Create React App | 快速启动 |

### 3.3 MCP 工具层

| 功能 | 实现方式 | 说明 |
|------|---------|------|
| **导航功能** | Java MCP Server (现有) | • 你已完成的 POC<br>• 通过 HTTP 调用<br>• 控制 Android 模拟器 |
| **天气查询** | 直接调用公开 API | • 无需 MCP Server<br>• 使用免费天气 API<br>• 例如: OpenWeatherMap / 和风天气 |

---

## 4. 核心模块设计

### 4.1 LangGraph Workflow

**State 定义**:
```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """Multi-Agent 共享状态"""

    # 消息历史
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 下一个要执行的 Agent
    next_agent: str

    # 已完成的任务列表
    completed_tasks: list

    # 会话 ID
    thread_id: str
```

**Workflow 结构**:
```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("supervisor", supervisor_agent)
workflow.add_node("navigation", navigation_agent)
workflow.add_node("weather", weather_agent)

# 入口
workflow.set_entry_point("supervisor")

# Supervisor 的条件路由
workflow.add_conditional_edges(
    "supervisor",
    lambda state: state["next_agent"],
    {
        "navigation": "navigation",
        "weather": "weather",
        "finish": END,
    }
)

# Agent 完成后回到 Supervisor
workflow.add_edge("navigation", "supervisor")
workflow.add_edge("weather", "supervisor")

# 编译
app = workflow.compile(checkpointer=memory)
```

### 4.2 Agent 设计

#### 4.2.1 Supervisor Agent

**职责**:
- 分析用户意图
- 任务分解
- 选择合适的 Agent
- 汇总结果

**实现逻辑**:
```python
def supervisor_agent(state: AgentState) -> AgentState:
    """Supervisor: 任务分析和路由"""

    messages = state["messages"]
    last_message = messages[-1].content
    completed_tasks = state.get("completed_tasks", [])

    # LLM 决策
    prompt = f"""
你是任务调度专家。分析用户需求并选择合适的 Agent。

用户消息: {last_message}
已完成任务: {completed_tasks}

可用的 Agent:
- navigation: 处理导航、路线规划相关任务
- weather: 查询天气信息
- finish: 所有任务已完成

请分析用户意图,返回下一个要调用的 Agent 名称。
如果所有任务已完成,返回 "finish"。
"""

    response = llm.invoke(prompt)
    next_agent = response.content.strip().lower()

    return {
        "messages": [AIMessage(content=f"[Supervisor] 决定调用: {next_agent}")],
        "next_agent": next_agent,
    }
```

#### 4.2.2 Navigation Agent

**职责**:
- 理解导航需求
- 调用导航相关 MCP Tools
- 返回导航结果

**可用 Tools**:
- `plan_route(origin, destination, preference)` - 规划路线
- `start_navigation(destination)` - 启动导航

**实现**:
```python
from langchain.agents import create_tool_calling_agent

navigation_agent_executor = create_tool_calling_agent(
    llm,
    navigation_tools,  # [plan_route, start_navigation]
    navigation_prompt
)

def navigation_agent(state: AgentState) -> AgentState:
    """Navigation Agent: 处理导航任务"""

    result = navigation_agent_executor.invoke({
        "messages": state["messages"],
    })

    completed_tasks = state.get("completed_tasks", [])
    completed_tasks.append("navigation")

    return {
        "messages": [AIMessage(content=result["output"])],
        "completed_tasks": completed_tasks,
        "next_agent": "supervisor",
    }
```

#### 4.2.3 Weather Agent

**职责**:
- 理解天气查询需求
- 调用天气 API
- 返回天气信息

**可用 Tools**:
- `get_weather(city)` - 查询指定城市天气

**实现**:
```python
weather_agent_executor = create_tool_calling_agent(
    llm,
    weather_tools,  # [get_weather]
    weather_prompt
)

def weather_agent(state: AgentState) -> AgentState:
    """Weather Agent: 查询天气"""

    result = weather_agent_executor.invoke({
        "messages": state["messages"],
    })

    completed_tasks = state.get("completed_tasks", [])
    completed_tasks.append("weather")

    return {
        "messages": [AIMessage(content=result["output"])],
        "completed_tasks": completed_tasks,
        "next_agent": "supervisor",
    }
```

### 4.3 MCP Tools 实现

#### 4.3.1 导航 Tools (调用 Java MCP Server)

```python
from langchain_core.tools import tool
import requests

MCP_SERVER_URL = "http://localhost:8080"  # Java MCP Server 地址

@tool
def plan_route(origin: str, destination: str, preference: str = "fastest") -> str:
    """
    规划导航路线

    Args:
        origin: 起点
        destination: 终点
        preference: 路线偏好 (fastest/shortest/avoid_highway)

    Returns:
        路线信息
    """
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/mcp/invoke",
            json={
                "tool": "navigation.plan_route",
                "params": {
                    "origin": origin,
                    "destination": destination,
                    "preference": preference
                }
            },
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        return f"""
导航路线已规划:
- 起点: {origin}
- 终点: {destination}
- 距离: {result.get('distance', 'N/A')} km
- 预计时间: {result.get('duration', 'N/A')} 分钟

✅ 模拟器上的导航应用已开始导航
"""
    except Exception as e:
        return f"导航规划失败: {str(e)}"

@tool
def start_navigation(destination: str) -> str:
    """
    启动导航到目的地

    Args:
        destination: 目的地

    Returns:
        导航启动结果
    """
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/mcp/invoke",
            json={
                "tool": "navigation.start",
                "params": {"destination": destination}
            },
            timeout=10
        )
        response.raise_for_status()

        return f"✅ 已启动导航至: {destination}\n模拟器上的导航应用正在运行"
    except Exception as e:
        return f"启动导航失败: {str(e)}"

navigation_tools = [plan_route, start_navigation]
```

#### 4.3.2 天气 Tools (直接调用 API)

**选项 1: OpenWeatherMap (推荐)**
```python
@tool
def get_weather(city: str) -> str:
    """
    查询指定城市的天气

    Args:
        city: 城市名称 (中文或英文)

    Returns:
        天气信息
    """
    try:
        # 使用 OpenWeatherMap API (免费版)
        api_key = os.getenv("OPENWEATHER_API_KEY")
        url = f"https://api.openweathermap.org/data/2.5/weather"

        params = {
            "q": city,
            "appid": api_key,
            "units": "metric",  # 摄氏度
            "lang": "zh_cn"     # 中文
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return f"""
{city} 当前天气:
- 温度: {data['main']['temp']}°C
- 体感温度: {data['main']['feels_like']}°C
- 天气: {data['weather'][0]['description']}
- 湿度: {data['main']['humidity']}%
- 风速: {data['wind']['speed']} m/s
"""
    except Exception as e:
        return f"查询天气失败: {str(e)}"

weather_tools = [get_weather]
```

**选项 2: 和风天气 (国内更快)**
```python
@tool
def get_weather(city: str) -> str:
    """查询天气 - 和风天气 API"""
    try:
        api_key = os.getenv("QWEATHER_API_KEY")

        # 1. 先获取城市 ID
        location_url = "https://geoapi.qweather.com/v2/city/lookup"
        location_params = {"location": city, "key": api_key}
        loc_resp = requests.get(location_url, params=location_params)
        loc_data = loc_resp.json()

        if loc_data['code'] != '200':
            return f"未找到城市: {city}"

        location_id = loc_data['location'][0]['id']

        # 2. 查询天气
        weather_url = "https://devapi.qweather.com/v7/weather/now"
        weather_params = {"location": location_id, "key": api_key}
        weather_resp = requests.get(weather_url, params=weather_params)
        weather_data = weather_resp.json()

        now = weather_data['now']

        return f"""
{city} 当前天气:
- 温度: {now['temp']}°C
- 体感温度: {now['feelsLike']}°C
- 天气: {now['text']}
- 湿度: {now['humidity']}%
- 风向: {now['windDir']} {now['windScale']}级
"""
    except Exception as e:
        return f"查询天气失败: {str(e)}"
```

### 4.4 FastAPI 接口设计

#### 4.4.1 SSE 流式接口

```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json

@router.post("/chat/stream")
async def chat_stream(request: Request):
    """SSE 流式 Chat 接口"""

    body = await request.json()
    user_message = body.get("message")
    thread_id = body.get("thread_id", "default")

    app = create_workflow()

    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "thread_id": thread_id,
    }

    async def event_generator():
        """生成 SSE 事件"""
        try:
            async for event in app.astream_events(initial_state, config, version="v2"):

                # LLM 输出流
                if event["event"] == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                # Tool 开始
                elif event["event"] == "on_tool_start":
                    tool_name = event["name"]
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name})}\n\n"

                # Tool 完成
                elif event["event"] == "on_tool_end":
                    tool_name = event["name"]
                    result = event["data"]["output"]
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name, 'result': result})}\n\n"

                # 完成
                elif event["event"] == "on_chain_end":
                    if event["name"] == "LangGraph":
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### 4.5 前端流式处理

**自定义 Hook: useLangGraphStream**

```typescript
// frontend/src/hooks/useLangGraphStream.ts
import { useState, useCallback } from 'react';

interface Message {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  toolName?: string;
}

export const useLangGraphStream = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (userMessage: string) => {
    // 添加用户消息
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          thread_id: 'demo-thread-001',
        }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let assistantMessage = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'token') {
              // LLM 输出
              assistantMessage += data.content;
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];

                if (lastMsg?.role === 'assistant') {
                  lastMsg.content = assistantMessage;
                } else {
                  newMessages.push({ role: 'assistant', content: assistantMessage });
                }
                return newMessages;
              });
            }
            else if (data.type === 'tool_start') {
              // Tool 调用开始
              setMessages(prev => [...prev, {
                role: 'tool',
                content: '正在调用工具...',
                toolName: data.tool,
              }]);
            }
            else if (data.type === 'tool_end') {
              // Tool 调用完成
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg?.role === 'tool') {
                  lastMsg.content = data.result;
                }
                return newMessages;
              });
            }
            else if (data.type === 'done') {
              setIsLoading(false);
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream error:', error);
      setIsLoading(false);
    }
  }, []);

  return { messages, isLoading, sendMessage };
};
```

---

## 5. 项目结构

```
navigation-agent-chat/
├── README.md                       # 项目说明
├── docker-compose.yml              # Docker 编排
├── navigation-agent-architecture.md # 本架构文档
│
├── backend/                        # Python 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI 入口
│   │   │
│   │   ├── api/                   # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── chat.py           # Chat 接口 (SSE)
│   │   │   └── health.py         # 健康检查
│   │   │
│   │   ├── agents/                # Agent 实现
│   │   │   ├── __init__.py
│   │   │   ├── supervisor.py     # Supervisor Agent
│   │   │   ├── navigation.py     # Navigation Agent
│   │   │   └── weather.py        # Weather Agent
│   │   │
│   │   ├── graph/                 # LangGraph 定义
│   │   │   ├── __init__.py
│   │   │   └── workflow.py       # Workflow 构建
│   │   │
│   │   ├── tools/                 # MCP Tools
│   │   │   ├── __init__.py
│   │   │   ├── mcp_client.py     # MCP 客户端封装
│   │   │   ├── navigation_tools.py  # 导航工具
│   │   │   └── weather_tools.py  # 天气工具
│   │   │
│   │   ├── state/                 # 状态定义
│   │   │   ├── __init__.py
│   │   │   └── agent_state.py    # AgentState
│   │   │
│   │   └── config.py              # 配置管理
│   │
│   ├── data/                      # 数据目录
│   │   └── checkpoints.db        # SQLite 持久化
│   │
│   ├── requirements.txt           # Python 依赖
│   ├── .env.example              # 环境变量模板
│   └── Dockerfile                # Docker 镜像
│
├── frontend/                      # React 前端
│   ├── public/
│   │   └── index.html
│   │
│   ├── src/
│   │   ├── App.tsx               # 主应用
│   │   │
│   │   ├── components/           # 组件
│   │   │   ├── ChatInterface.tsx    # Chat 界面
│   │   │   ├── MessageList.tsx      # 消息列表
│   │   │   └── MessageItem.tsx      # 单条消息
│   │   │
│   │   ├── hooks/                # 自定义 Hooks
│   │   │   └── useLangGraphStream.ts  # Stream Hook
│   │   │
│   │   ├── types/                # TypeScript 类型
│   │   │   └── message.ts
│   │   │
│   │   └── utils/                # 工具函数
│   │       └── api.ts
│   │
│   ├── package.json              # NPM 依赖
│   ├── tsconfig.json             # TypeScript 配置
│   └── tailwind.config.js        # Tailwind CSS 配置
│
└── docs/                          # 文档
    ├── api.md                    # API 文档
    ├── deployment.md             # 部署文档
    └── testing.md                # 测试文档
```

---

## 6. 实现路线图

### Phase 1: 后端基础 (Week 1-2)

**目标**: 搭建 LangGraph Multi-Agent 系统

**任务清单**:
- [ ] 初始化项目结构
- [ ] 实现 `AgentState` 定义
- [ ] 实现 Supervisor Agent (基础版)
- [ ] 实现 Navigation Agent
- [ ] 实现 Weather Agent
- [ ] 实现导航 MCP Tools (连接 Java Server)
- [ ] 实现天气 Tools (调用 API)
- [ ] 构建 LangGraph Workflow
- [ ] 测试 Workflow (命令行)

**验收标准**:
```bash
# 能在命令行测试
python test_workflow.py

输入: "导航到首都机场"
输出:
- [Supervisor] 决定调用: navigation
- [Navigation Agent] 正在规划路线...
- [Tool] plan_route 调用成功
- ✅ 模拟器已开始导航
```

### Phase 2: FastAPI 接口 (Week 3)

**目标**: 实现 REST API 和 SSE 流式接口

**任务清单**:
- [ ] 创建 FastAPI 应用
- [ ] 实现 `/api/chat` 标准接口
- [ ] 实现 `/api/chat/stream` SSE 接口
- [ ] 添加 CORS 中间件
- [ ] 实现健康检查接口
- [ ] 添加错误处理
- [ ] 测试 SSE 流式响应

**验收标准**:
```bash
# 测试标准接口
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "导航到首都机场"}'

# 测试流式接口
curl -N http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "导航到首都机场"}'

# 应该看到实时流式输出
```

### Phase 3: React 前端 (Week 4)

**目标**: 实现 Chat UI 界面

**任务清单**:
- [ ] 初始化 React 项目 (CRA + TypeScript)
- [ ] 实现 `useLangGraphStream` Hook
- [ ] 实现 `ChatInterface` 组件
- [ ] 实现 `MessageList` 组件
- [ ] 实现流式消息渲染
- [ ] 添加加载状态显示
- [ ] 添加错误处理
- [ ] UI 样式优化 (Tailwind CSS)

**验收标准**:
- 用户能在网页输入消息
- 实时看到 Agent 执行过程
- Tool 调用状态可见
- 最终结果清晰展示

### Phase 4: 集成测试 (Week 5)

**目标**: 端到端测试和优化

**任务清单**:
- [ ] 场景 1: 单一导航任务测试
- [ ] 场景 2: 单一天气查询测试
- [ ] 场景 3: 复合任务测试
- [ ] 错误场景测试 (MCP Server 不可用)
- [ ] 性能优化 (响应速度)
- [ ] 日志和监控
- [ ] 编写使用文档

### Phase 5: 部署 (Week 6)

**任务清单**:
- [ ] Docker 化
- [ ] docker-compose 编排
- [ ] 环境变量配置
- [ ] 生产环境部署文档

---

## 7. 测试场景

### 7.1 场景 1: 单一导航任务

**输入**:
```
用户: "导航到首都机场"
```

**预期执行流程**:
```
1. Supervisor 分析: 识别为导航任务
2. Supervisor 决策: next_agent = "navigation"
3. Navigation Agent 被调用
4. Navigation Agent 调用 plan_route Tool
5. MCP Client 发送 HTTP 请求到 Java MCP Server
6. Java MCP Server 控制 Android 模拟器启动导航
7. 返回结果: "✅ 已为您规划路线..."
8. Supervisor 判断任务完成,返回最终结果
```

**前端显示**:
```
用户: 导航到首都机场

[Supervisor] 正在分析任务...

[Navigation Agent] 正在规划路线...

🔧 调用工具: plan_route
起点: 当前位置
终点: 首都机场

✅ 路线规划成功:
- 距离: 28.5 km
- 预计时间: 35 分钟
- 模拟器上的导航应用已开始导航
```

### 7.2 场景 2: 单一天气查询

**输入**:
```
用户: "北京今天天气怎么样"
```

**预期执行流程**:
```
1. Supervisor 分析: 识别为天气查询
2. Supervisor 决策: next_agent = "weather"
3. Weather Agent 被调用
4. Weather Agent 调用 get_weather Tool
5. 直接调用天气 API (OpenWeatherMap / 和风天气)
6. 返回天气信息
7. Supervisor 判断任务完成
```

**前端显示**:
```
用户: 北京今天天气怎么样

[Supervisor] 正在分析任务...

[Weather Agent] 正在查询天气...

🔧 调用工具: get_weather

北京 当前天气:
- 温度: 15°C
- 体感温度: 13°C
- 天气: 晴
- 湿度: 45%
- 风速: 3 m/s
```

### 7.3 场景 3: 复合任务

**输入**:
```
用户: "导航到首都机场,顺便查一下那边的天气"
```

**预期执行流程**:
```
1. Supervisor 分析: 识别两个任务
   - 任务1: 导航到首都机场
   - 任务2: 查询首都机场天气

2. Supervisor 决策: 先执行 navigation

3. Navigation Agent 执行完成
   completed_tasks = ["navigation"]

4. 回到 Supervisor,判断还有任务未完成

5. Supervisor 决策: 执行 weather

6. Weather Agent 执行完成
   completed_tasks = ["navigation", "weather"]

7. 回到 Supervisor,判断所有任务完成

8. Supervisor 返回最终结果
```

**前端显示**:
```
用户: 导航到首都机场,顺便查一下那边的天气

[Supervisor] 正在分析任务...
识别到 2 个任务: 导航 + 天气查询

[Navigation Agent] 正在规划路线...
✅ 路线规划成功 (28.5km, 35分钟)
✅ 模拟器导航已启动

[Weather Agent] 正在查询天气...
首都机场附近天气:
- 温度: 14°C
- 天气: 多云
- 湿度: 50%

✅ 所有任务已完成!
```

### 7.4 错误场景测试

**场景 4A: Java MCP Server 不可用**

```
用户: "导航到首都机场"

[Navigation Agent] 正在规划路线...
🔧 调用工具: plan_route

❌ 导航规划失败: 连接到 MCP Server 超时
提示: 请检查导航服务是否正常运行
```

**场景 4B: 天气 API 调用失败**

```
用户: "查询火星的天气"

[Weather Agent] 正在查询天气...
🔧 调用工具: get_weather

❌ 查询天气失败: 未找到城市 "火星"
```

---

## 8. 部署方案

### 8.1 开发环境

**启动顺序**:

```bash
# 1. 启动 Java MCP Server (你现有的)
cd /path/to/java-mcp-server
java -jar mcp-server.jar

# 2. 启动后端
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 配置环境变量
cat > .env << EOF
OPENAI_API_KEY=your-openai-key
OPENWEATHER_API_KEY=your-weather-key
MCP_SERVER_URL=http://localhost:8080
EOF

uvicorn app.main:app --reload

# 3. 启动前端
cd frontend
npm install
npm start
```

**访问**:
- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 8.2 Docker 部署

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY}
      - MCP_SERVER_URL=http://mcp-server:8080
    volumes:
      - ./backend:/app
      - ./data:/app/data
    depends_on:
      - mcp-server
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    restart: unless-stopped

  mcp-server:
    # 你现有的 Java MCP Server
    image: your-mcp-server:latest
    ports:
      - "8080:8080"
    restart: unless-stopped
```

**启动**:
```bash
# 一键启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 8.3 环境变量配置

**backend/.env.example**:
```bash
# OpenAI API
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4

# 天气 API (选择一个)
OPENWEATHER_API_KEY=your-key  # OpenWeatherMap
# 或
QWEATHER_API_KEY=your-key     # 和风天气

# MCP Server
MCP_SERVER_URL=http://localhost:8080

# 数据库
DATABASE_URL=sqlite:///./data/checkpoints.db
```

---

## 9. 关键技术决策记录

### 9.1 Multi-Agent 模式选择

**决策**: Supervisor 模式

**备选方案**:
- Swarm 模式: 去中心化,延迟更低,但难以调试
- Hierarchical 模式: 适合大型系统,但当前不需要

**选择理由**:
1. ✅ 学习友好: 官方主推,文档最丰富
2. ✅ 车载适配: 中心化控制,安全可控
3. ✅ 调试容易: 流程清晰,易于追踪
4. ✅ 扩展性好: 易于添加新 Agent

### 9.2 通信协议选择

**决策**: SSE (Server-Sent Events)

**备选方案**:
- WebSocket: 双向通信,但实现更复杂
- 短轮询: 简单但低效

**选择理由**:
1. ✅ 单向流式: 符合 Chat 场景
2. ✅ 实现简单: HTTP 协议,自动重连
3. ✅ 浏览器原生支持: EventSource API
4. ✅ LangGraph 官方推荐

### 9.3 天气功能实现方式

**决策**: 直接调用公开 API,不使用 MCP Server

**理由**:
1. ✅ 简化架构: 无需额外的 MCP Server
2. ✅ 快速开发: 直接封装为 Tool
3. ✅ 成本低: 免费 API 足够使用
4. ✅ 维护简单: 减少依赖

**推荐 API**:
- **OpenWeatherMap**: 国际通用,免费额度充足
- **和风天气**: 国内访问快,中文支持好

---

## 10. 下一步行动

### 10.1 立即开始

**明天的任务**:

1. **创建项目结构**
   ```bash
   mkdir -p navigation-agent-chat/{backend,frontend,docs}
   cd navigation-agent-chat/backend
   mkdir -p app/{api,agents,graph,tools,state}
   ```

2. **初始化后端**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install fastapi uvicorn langchain langchain-openai langgraph requests python-dotenv
   pip freeze > requirements.txt
   ```

3. **实现第一个 Agent**
   - 从 Weather Agent 开始(更简单,无需 MCP Server)
   - 测试 Tool 调用
   - 验证 LangGraph Workflow

### 10.2 学习资源

**必看文档**:
- LangGraph 官方教程: https://langchain-ai.github.io/langgraph/tutorials/
- Agent Supervisor 示例: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
- FastAPI SSE: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse

**参考项目**:
- LangGraph Examples: https://github.com/langchain-ai/langgraph-example

### 10.3 里程碑

- ✅ **Week 2**: 命令行能跑通 Multi-Agent
- ✅ **Week 3**: FastAPI SSE 接口可用
- ✅ **Week 4**: Web 界面能对话
- ✅ **Week 5**: 完整功能测试通过

---

## 11. 附录

### 11.1 常见问题

**Q1: LangGraph 的 checkpointing 有什么用?**

A: 保存 Agent 执行的中间状态,支持:
- 对话历史持久化
- 中断后恢复
- 多轮对话上下文

**Q2: 为什么 Navigation Agent 和 Weather Agent 都要回到 Supervisor?**

A: Supervisor 模式的核心设计,所有决策都由 Supervisor 做:
- 判断任务是否完成
- 决定下一步执行哪个 Agent
- 汇总最终结果

**Q3: SSE 和 WebSocket 的区别?**

| 特性 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 单向 (服务器→客户端) | 双向 |
| 协议 | HTTP | WS |
| 重连 | 自动 | 需手动实现 |
| 浏览器支持 | 原生 EventSource | 原生 WebSocket |
| 适用场景 | 流式输出,通知推送 | 实时协作,游戏 |

**Q4: 如何获取天气 API Key?**

**OpenWeatherMap**:
1. 注册: https://openweathermap.org/api
2. 免费额度: 60次/分钟, 1,000,000次/月
3. 获取 API Key

**和风天气**:
1. 注册: https://dev.qweather.com/
2. 免费额度: 1000次/天
3. 获取 API Key

### 11.2 项目依赖版本

**Python (backend)**:
```
Python >= 3.10
fastapi == 0.109.0
uvicorn[standard] == 0.27.0
langchain == 0.1.0
langchain-openai == 0.0.5
langgraph == 0.0.20
requests == 2.31.0
python-dotenv == 1.0.0
aiosqlite == 0.19.0
```

**Node.js (frontend)**:
```
Node.js >= 18
React >= 18.2.0
TypeScript >= 5.0.0
```

### 11.3 Git 忽略文件

**.gitignore**:
```
# Python
__pycache__/
*.py[cod]
*$py.class
venv/
.env

# Node
node_modules/
build/
.DS_Store

# Data
data/
*.db
*.log

# IDE
.vscode/
.idea/
```

---

## 结语

这份文档记录了我们从零开始设计导航多智能体系统的完整思路:

1. ✅ **明确目标**: Web 对话 + 导航控制 + 天气查询
2. ✅ **架构选型**: Supervisor 模式 + FastAPI + React
3. ✅ **技术决策**: SSE 流式 + 直接调用天气 API
4. ✅ **实施计划**: 6周分阶段完成

**核心价值**:
- 深入学习 LangGraph
- 掌握 Multi-Agent 实践
- 构建真实可用的系统

**开始时间**: 明天
**第一步**: 实现 Weather Agent

祝开发顺利! 🚀
