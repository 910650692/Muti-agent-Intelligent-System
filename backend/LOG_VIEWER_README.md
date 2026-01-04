# 日志查看工具使用指南

## 快速开始

```bash
# 查看今天的日志
python view_logs.py

# 查看指定日期的日志
python view_logs.py --date 20251230

# 列出所有日志文件
python view_logs.py --list
```

## 功能特性

### ✅ 美化显示
- 彩色输出，易于阅读
- 时间戳格式化（精确到毫秒）
- 日志级别高亮显示

### ✅ 过滤功能
- 按用户过滤：`--user user_001`
- 按对话过滤：`--conversation conv_123`
- 按日志级别过滤：`--level ERROR`
- 关键词搜索：`--search "记忆"`

### ✅ 实时跟踪
- 类似 `tail -f`：`--follow`

### ✅ 详细模式
- 显示完整信息：`--detailed`

## 常用命令

### 基础查看

```bash
# 查看今天的普通日志
python view_logs.py

# 查看今天的错误日志
python view_logs.py --error

# 查看指定日期
python view_logs.py --date 20251230
```

### 过滤查看

```bash
# 只看错误和警告
python view_logs.py --level ERROR
python view_logs.py --level WARNING

# 只看特定用户的日志
python view_logs.py --user user_001

# 只看特定对话的日志
python view_logs.py --conversation 7e234a5b-1234-5678-9abc-def012345678
```

### 搜索功能

```bash
# 搜索包含"记忆"的日志
python view_logs.py --search "记忆"

# 搜索包含"HITL"的日志
python view_logs.py --search "HITL"

# 搜索工具调用
python view_logs.py --search "memory_save"
```

### 实时跟踪

```bash
# 实时跟踪今天的日志（按 Ctrl+C 停止）
python view_logs.py --follow

# 实时跟踪错误日志
python view_logs.py --error --follow

# 实时跟踪并过滤特定用户
python view_logs.py --follow --user user_001
```

### 详细模式

```bash
# 显示每条日志的完整详细信息
python view_logs.py --detailed

# 详细模式 + 搜索
python view_logs.py --detailed --search "detected_memories"
```

### 组合使用

```bash
# 查看特定用户的错误日志
python view_logs.py --user user_001 --level ERROR

# 搜索特定对话中包含"记忆"的日志
python view_logs.py --conversation conv_123 --search "记忆"

# 实时跟踪特定用户的详细日志
python view_logs.py --follow --user user_001 --detailed
```

## 输出格式说明

### 普通模式
```
10:30:15.123 INFO     [user=user_001 conv=7e234a5b] 推理开始  iteration=1, message_count=3
```

### 详细模式
```
================================================================================
时间: 2025-12-31T10:30:15.123456+08:00
级别: INFO
事件: 推理开始
用户: user_001
对话ID: 7e234a5b-1234-5678-9abc-def012345678
请求ID: req_abc123

详细信息:
  iteration: 1
  message_count: 3
  tool_calls: 0
================================================================================
```

## 颜色说明

- **蓝色**：时间戳和上下文信息
- **青色**：INFO 级别
- **黄色**：WARNING 级别
- **红色**：ERROR 级别
- **红底白字**：CRITICAL 级别
- **灰色**：次要信息（文件位置等）

## 调试场景示例

### 场景 1：调试记忆检测问题

```bash
# 搜索记忆相关的所有日志
python view_logs.py --search "detected_memories" --detailed

# 查看记忆保存失败的错误
python view_logs.py --search "memory_save" --level ERROR
```

### 场景 2：追踪特定对话

```bash
# 获取对话ID（从前端或数据库）
# 然后查看该对话的所有日志
python view_logs.py --conversation 7e234a5b-1234-5678-9abc-def012345678 --detailed
```

### 场景 3：监控生产环境

```bash
# 实时监控错误日志
python view_logs.py --error --follow

# 实时监控特定用户的所有活动
python view_logs.py --user user_001 --follow
```

### 场景 4：查找性能问题

```bash
# 搜索超时相关的日志
python view_logs.py --search "timeout"

# 搜索工具调用失败
python view_logs.py --search "failed" --level ERROR
```

## 快捷别名（可选）

在你的 shell 配置文件（如 `.bashrc` 或 `.zshrc`）中添加：

```bash
alias logs='python backend/view_logs.py'
alias logs-error='python backend/view_logs.py --error'
alias logs-follow='python backend/view_logs.py --follow'
alias logs-detail='python backend/view_logs.py --detailed'
```

然后就可以：

```bash
logs                    # 查看今天的日志
logs-error              # 查看错误日志
logs-follow             # 实时跟踪
logs-detail --search "HITL"  # 详细搜索
```

## 故障排查

### 问题：日志文件不存在

```
错误: 日志文件不存在: logs/app_20251231.log
```

**解决**：
1. 检查日志目录是否正确：`python view_logs.py --list`
2. 确认后端是否已运行并生成日志
3. 使用 `--date` 指定存在的日期

### 问题：没有输出

**可能原因**：
1. 过滤条件太严格，没有匹配的日志
2. 日志文件为空

**解决**：
```bash
# 去掉所有过滤，看看是否有日志
python view_logs.py

# 检查日志文件大小
python view_logs.py --list
```

### 问题：输出乱码

**解决**：确保终端支持 UTF-8 和 ANSI 颜色。

Windows 用户：使用 Windows Terminal 或更新的 PowerShell。

## 高级用法

### 导出为纯文本（去除颜色）

```bash
python view_logs.py --search "HITL" > output.txt
```

### 结合 grep 使用

```bash
python view_logs.py | grep "memory"
```

### 统计日志数量

```bash
python view_logs.py --level ERROR | wc -l
```

## 技术细节

- **解析格式**：JSON 格式的结构化日志
- **颜色支持**：ANSI 转义码
- **字符编码**：UTF-8
- **实时跟踪**：文件轮询（100ms 间隔）

## 后续改进计划

- [ ] 支持日期范围过滤
- [ ] 支持导出为 HTML 或 Markdown
- [ ] 添加统计分析功能（错误率、响应时间等）
- [ ] 支持多文件合并查看
- [ ] 添加交互式 TUI 界面
