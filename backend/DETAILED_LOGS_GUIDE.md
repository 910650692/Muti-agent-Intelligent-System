# 详细日志指南

## 新增的日志类型（Emoji 标记）

为了方便调试和追踪对话流程，我们在 Agent V2 中添加了详细的日志，使用 Emoji 标记不同类型的日志：

### 📥 用户输入
记录每轮用户发送的完整消息

```json
{
  "event": "📥 用户输入",
  "iteration": 1,
  "user_message": "我喜欢听音乐",
  "message_type": "HumanMessage"
}
```

**查看方式**：
```bash
python view_logs.py --search "📥 用户输入" --detailed
```

---

### 📸 Messages 快照（DEBUG 级别）
记录每轮推理前的完整 messages 数组（用于深度调试）

```json
{
  "event": "📸 Messages 快照",
  "iteration": 1,
  "messages": [
    {"type": "HumanMessage", "content": "我喜欢听音乐", "has_tool_calls": false},
    {"type": "AIMessage", "content": "很高兴认识你！...", "has_tool_calls": false}
  ]
}
```

**查看方式**（需要设置 DEBUG 级别）：
```bash
# 修改 main.py 中的日志级别为 DEBUG
python view_logs.py --search "📸 Messages" --detailed
```

---

### 📤 LLM 原始输出
记录 LLM 返回的原始 content 和 tool_calls

```json
{
  "event": "📤 LLM 原始输出",
  "iteration": 1,
  "content": "很高兴认识你！程序员加运动爱好者...\n\n__DETECTED_MEMORIES__\n[...]\n__END_DETECTED_MEMORIES__",
  "tool_calls_count": 0,
  "has_tool_calls": false
}
```

**查看方式**：
```bash
python view_logs.py --search "📤 LLM 原始输出" --detailed
```

---

### 📊 Decision 详情
记录解析后的 decision 对象（think、response、actions、detected_memories）

```json
{
  "event": "📊 Decision 详情",
  "iteration": 1,
  "think": "用户表达了对音乐的兴趣爱好",
  "response": "很高兴认识你！程序员加运动爱好者，这组合不错！",
  "actions": [],
  "is_complete": true,
  "has_detected_memories": true
}
```

**查看方式**：
```bash
python view_logs.py --search "📊 Decision" --detailed
```

**作用**：
- 查看 Agent 的推理过程（think）
- 查看 Agent 准备回复的内容（response）
- 查看 Agent 决定调用的工具（actions）
- 查看是否检测到记忆（has_detected_memories）

---

### 🧠 检测到记忆
记录 detected_memories 的完整内容

```json
{
  "event": "🧠 检测到记忆",
  "iteration": 1,
  "detected_memories": [
    {
      "type": "profile",
      "data": {"interests": ["音乐"]},
      "confidence": "high"
    }
  ]
}
```

**查看方式**：
```bash
python view_logs.py --search "🧠 检测到记忆" --detailed
```

---

### 🛠️ 工具调用
记录工具调用的详细参数

```json
{
  "event": "🛠️ 工具调用",
  "tool_name": "memory_save_preference",
  "args": {
    "user_id": "user_001",
    "category": "music",
    "key": "favorite_genres",
    "value": "R&B,流行"
  },
  "tool_call_id": "call_abc123"
}
```

**查看方式**：
```bash
python view_logs.py --search "🛠️ 工具调用" --detailed
```

---

### 🔧 工具返回值
记录工具执行后的返回值

```json
{
  "event": "🔧 工具返回值",
  "tool_name": "memory_save_preference",
  "result": "偏好已保存：music/favorite_genres = R&B,流行",
  "result_length": 45
}
```

**查看方式**：
```bash
python view_logs.py --search "🔧 工具返回值" --detailed
```

**注意**：
- 如果返回值超过 500 字符，会截断显示（但会记录完整长度）
- 如需查看完整返回值，查看详细模式的 JSON

---

### 📮 最终响应
记录最终返回给用户的完整内容

```json
{
  "event": "📮 最终响应",
  "response": "好的，已经记住你喜欢 R&B 和流行音乐了！下次可以为你推荐相关的歌曲。",
  "response_length": 42
}
```

**查看方式**：
```bash
python view_logs.py --search "📮 最终响应" --detailed
```

---

## 完整对话流程追踪

### 场景 1：追踪记忆检测和保存

**步骤**：
```bash
# 1. 查看用户输入了什么
python view_logs.py --search "📥 用户输入" --conversation conv_176

# 2. 查看 LLM 的原始输出（包含 detected_memories 标记）
python view_logs.py --search "📤 LLM 原始输出" --conversation conv_176 --detailed

# 3. 查看解析后的 Decision
python view_logs.py --search "📊 Decision" --conversation conv_176 --detailed

# 4. 查看检测到的记忆
python view_logs.py --search "🧠 检测到记忆" --conversation conv_176 --detailed

# 5. 查看最终响应
python view_logs.py --search "📮 最终响应" --conversation conv_176
```

### 场景 2：追踪工具调用流程

**步骤**：
```bash
# 1. 查看用户输入
python view_logs.py --search "📥 用户输入" --conversation conv_176

# 2. 查看 Decision 中的 actions
python view_logs.py --search "📊 Decision" --conversation conv_176 --detailed

# 3. 查看工具调用的参数
python view_logs.py --search "🛠️ 工具调用" --conversation conv_176 --detailed

# 4. 查看工具返回值
python view_logs.py --search "🔧 工具返回值" --conversation conv_176 --detailed

# 5. 查看最终响应
python view_logs.py --search "📮 最终响应" --conversation conv_176
```

### 场景 3：查看完整的 ReAct 循环

**查看特定对话的所有日志**：
```bash
python view_logs.py --conversation conv_176 --detailed > conv_176_full.log
```

然后在文件中搜索 Emoji 标记，按顺序查看：
1. 📥 用户输入 → 用户说了什么
2. 📤 LLM 原始输出 → LLM 的完整响应
3. 📊 Decision 详情 → 解析后的决策
4. 🧠 检测到记忆 → 记忆内容（如果有）
5. 🛠️ 工具调用 → 工具参数（如果有）
6. 🔧 工具返回值 → 工具结果（如果有）
7. 📮 最终响应 → 返回给用户的内容

---

## 调试技巧

### 1. 快速定位问题

```bash
# 查看今天所有错误
python view_logs.py --level ERROR

# 查看特定用户的所有错误
python view_logs.py --user user_001 --level ERROR

# 查看特定对话中的错误
python view_logs.py --conversation conv_176 --level ERROR
```

### 2. 对比多轮对话

```bash
# 查看第 1 轮的输入输出
python view_logs.py --conversation conv_176 --search "iteration=1" --detailed

# 查看第 2 轮的输入输出
python view_logs.py --conversation conv_176 --search "iteration=2" --detailed
```

### 3. 搜索关键内容

```bash
# 搜索包含"音乐"的所有日志
python view_logs.py --search "音乐" --detailed

# 搜索所有记忆相关的操作
python view_logs.py --search "memory" --detailed

# 搜索 HITL 相关的日志
python view_logs.py --search "HITL" --detailed
```

### 4. 实时监控

```bash
# 实时监控所有日志
python view_logs.py --follow

# 实时监控特定用户
python view_logs.py --user user_001 --follow

# 实时监控并高亮关键词
python view_logs.py --follow --search "记忆"
```

---

## 日志级别说明

当前项目使用的日志级别：

- **DEBUG**：详细的调试信息（如 Messages 快照）
- **INFO**：正常的操作记录（大部分日志）
- **WARNING**：警告信息（如达到循环次数上限）
- **ERROR**：错误信息（如工具调用失败）

**修改日志级别**：

在 `backend/app/main.py` 中修改：

```python
setup_structured_logging(
    log_level="DEBUG",  # 改为 DEBUG 可以看到 Messages 快照
    enable_json=True,
    enable_console=True
)
```

---

## 常见调试场景

### 问题 1：记忆没有被检测到

**排查步骤**：
```bash
# 1. 查看用户输入
python view_logs.py --search "📥 用户输入" --detailed

# 2. 查看 LLM 原始输出（检查是否有 __DETECTED_MEMORIES__ 标记）
python view_logs.py --search "📤 LLM 原始输出" --detailed

# 3. 查看 Decision 详情（检查 has_detected_memories）
python view_logs.py --search "📊 Decision" --detailed
```

### 问题 2：工具调用失败

**排查步骤**：
```bash
# 1. 查看工具调用参数
python view_logs.py --search "🛠️ 工具调用" --detailed

# 2. 查看错误日志
python view_logs.py --level ERROR --detailed

# 3. 查看工具返回值（如果成功）
python view_logs.py --search "🔧 工具返回值" --detailed
```

### 问题 3：回复内容不符合预期

**排查步骤**：
```bash
# 1. 查看 LLM 的 Decision（think 和 response）
python view_logs.py --search "📊 Decision" --detailed

# 2. 查看最终响应
python view_logs.py --search "📮 最终响应" --detailed

# 3. 对比两者，看是否有工具执行结果被追加
```

---

## 总结

使用这些详细日志，你可以：

1. ✅ 完整追踪每轮对话的输入输出
2. ✅ 查看 LLM 的原始响应和推理过程
3. ✅ 追踪工具调用的参数和返回值
4. ✅ 调试记忆检测和保存流程
5. ✅ 快速定位问题所在的节点

**不再需要去 Langfuse 查看，本地日志已经足够详细！**
