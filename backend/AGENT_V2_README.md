# Agent V2 使用说明

## Step 1 完成 ✓

已创建简化版Agent V2，支持标准化的decision输出格式。

## 如何切换版本

### 方法1：环境变量（推荐）

```bash
# 使用V2版本
export AGENT_VERSION=v2

# 或在启动时设置
AGENT_VERSION=v2 python -m uvicorn backend.app.main:app --reload

# 切换回V1
export AGENT_VERSION=v1
```

### 方法2：修改.env文件

在项目根目录的`.env`文件中添加：

```
AGENT_VERSION=v2
```

## 测试验证

### 测试1：纯对话（不调用工具）

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "conversation_id": "test_001"
  }'
```

**预期结果**：
- Agent推理：`actions: []`（无工具调用）
- 直接回复用户
- 跳过Execution Node
- 进入Response Node

---

### 测试2：对话任务（需要调用工具）

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我导航到首都国际机场",
    "conversation_id": "test_002"
  }'
```

**预期结果**：
- Agent推理：`actions: [{"name": "set_destination", "args": {...}}]`
- 进入Execution Node执行工具
- 工具执行成功/失败
- 进入Response Node返回结果

---

### 测试3：多轮ReAct（工具执行失败）

手动模拟工具失败场景，验证是否会循环重试。

---

## V1 vs V2 对比

| 特性 | V1（原版） | V2（简化版） |
|------|----------|------------|
| **代码行数** | ~800行 | ~420行 |
| **支持多模态** | ✅ 是 | ❌ 否 |
| **HITL确认** | ✅ 复杂 | ⏸ 待添加 |
| **置信度门控** | ✅ 有 | ❌ 无 |
| **decision输出** | ❌ 无 | ✅ 有 |
| **Node分离** | ⚠️ 部分 | ✅ 清晰 |
| **易于扩展** | ⚠️ 困难 | ✅ 容易 |
| **适合场景** | 生产环境 | Demo/学习 |

## 架构图（V2）

```
用户输入
  ↓
[Agent Node] - LLM推理
  - 读取: messages, action_results
  - 推理: 调用哪些工具？
  - 输出: decision {think, actions, response, is_complete}
  ↓
[Conditional Edge: should_continue]
  ↙                    ↘
有工具                 无工具
  ↓                     ↓
[Execution Node]    [Response Node]
  - 遍历actions         ↓
  - 调用MCP工具        END
  - 收集结果
  ↓
[Conditional Edge: need_continue_after_execution]
  ↙                    ↘
有错误                 成功
  ↓                     ↓
回Agent重新推理    [Response Node]
(ReAct循环)             ↓
                      END
```

## 下一步（Step 2）

添加独立的Execution Node增强功能：
- [ ] 工具元数据管理（哪些工具需要HITL）
- [ ] HITL确认集成
- [ ] 用户反馈记录

## 常见问题

### Q1: V2版本报错找不到模块？

A: 确保已重启后端服务：
```bash
# 停止现有服务
Ctrl+C

# 重新启动
AGENT_VERSION=v2 python -m uvicorn backend.app.main:app --reload
```

### Q2: 如何查看当前使用的版本？

A: 查看启动日志：
```
INFO - Agent已启动, agent_type=navigation_v2  ← V2版本
INFO - Agent已启动, agent_type=navigation_v1  ← V1版本
```

### Q3: V2版本支持图片输入吗？

A: 暂不支持。V2是简化版，专注于核心功能。需要多模态请使用V1。
