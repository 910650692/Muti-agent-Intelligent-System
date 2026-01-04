#!/usr/bin/env python
"""日志查看工具 - 解析和美化显示结构化日志

功能：
1. 解析 JSON 格式的日志文件
2. 美化显示对话内容
3. 支持过滤（时间、用户、对话ID、日志级别）
4. 显示完整的 LLM 输入输出
5. 对话流程追踪

使用方法：
    python view_logs.py                          # 查看今天的日志
    python view_logs.py --date 20251230          # 查看指定日期
    python view_logs.py --user user_001          # 过滤特定用户
    python view_logs.py --conversation conv_123  # 过滤特定对话
    python view_logs.py --level ERROR            # 只看错误日志
    python view_logs.py --follow                 # 实时跟踪（tail -f）
    python view_logs.py --search "记忆"          # 搜索关键词
"""
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import time

# 颜色代码（ANSI）
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # 基础颜色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 高亮颜色
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # 背景色
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


# 日志级别颜色映射
LEVEL_COLORS = {
    "DEBUG": Colors.DIM + Colors.WHITE,
    "INFO": Colors.BRIGHT_CYAN,
    "WARNING": Colors.BRIGHT_YELLOW,
    "ERROR": Colors.BRIGHT_RED,
    "CRITICAL": Colors.BG_RED + Colors.WHITE,
}


def parse_log_line(line: str) -> Optional[Dict]:
    """解析单行日志"""
    line = line.strip()
    if not line:
        return None

    try:
        return json.loads(line)
    except json.JSONDecodeError:
        # 不是 JSON，可能是普通文本日志
        return None


def format_timestamp(ts: str) -> str:
    """格式化时间戳"""
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.strftime("%H:%M:%S.%f")[:-3]  # 只保留毫秒
    except:
        return ts


def get_level_display(level: str) -> str:
    """获取带颜色的日志级别显示"""
    color = LEVEL_COLORS.get(level.upper(), Colors.WHITE)
    return f"{color}{level:8s}{Colors.RESET}"


def truncate(text: str, max_len: int = 100) -> str:
    """截断长文本"""
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


def format_log_entry(entry: Dict, show_full: bool = False, highlight: Optional[str] = None) -> str:
    """格式化单条日志"""
    timestamp = format_timestamp(entry.get("timestamp", ""))
    level = entry.get("level", "INFO").upper()
    event = entry.get("event", "")

    # 构建基础信息
    parts = []
    parts.append(f"{Colors.DIM}{timestamp}{Colors.RESET}")
    parts.append(get_level_display(level))

    # 添加上下文信息（如果有）
    context_parts = []
    if entry.get("user_id"):
        context_parts.append(f"{Colors.CYAN}user={entry['user_id']}{Colors.RESET}")
    if entry.get("conversation_id"):
        conv_id = entry['conversation_id'][:8]  # 只显示前8位
        context_parts.append(f"{Colors.MAGENTA}conv={conv_id}{Colors.RESET}")
    if entry.get("request_id"):
        req_id = entry['request_id'][:8]
        context_parts.append(f"{Colors.BLUE}req={req_id}{Colors.RESET}")

    if context_parts:
        parts.append(f"[{' '.join(context_parts)}]")

    # 添加事件信息
    event_text = event
    if highlight and highlight.lower() in event.lower():
        # 高亮搜索关键词
        event_text = event.replace(highlight, f"{Colors.BG_YELLOW}{Colors.BLACK}{highlight}{Colors.RESET}")

    parts.append(f"{Colors.BOLD}{event_text}{Colors.RESET}")

    # 添加额外字段
    exclude_fields = {'timestamp', 'level', 'event', 'user_id', 'conversation_id', 'request_id',
                      'filename', 'lineno', 'func_name'}
    extra_fields = {k: v for k, v in entry.items() if k not in exclude_fields}

    if extra_fields:
        extra_str = ", ".join([f"{Colors.DIM}{k}={v}{Colors.RESET}" for k, v in extra_fields.items()])
        if not show_full:
            extra_str = truncate(extra_str, 150)
        parts.append(f"  {extra_str}")

    return " ".join(parts)


def format_detailed_entry(entry: Dict) -> str:
    """格式化详细的日志条目（用于详细模式）"""
    lines = []
    lines.append(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    lines.append(f"{Colors.BRIGHT_CYAN}时间: {Colors.RESET}{entry.get('timestamp', 'N/A')}")
    lines.append(f"{Colors.BRIGHT_CYAN}级别: {Colors.RESET}{get_level_display(entry.get('level', 'INFO'))}")
    lines.append(f"{Colors.BRIGHT_CYAN}事件: {Colors.RESET}{Colors.BOLD}{entry.get('event', 'N/A')}{Colors.RESET}")

    # 上下文信息
    if entry.get("user_id"):
        lines.append(f"{Colors.BRIGHT_CYAN}用户: {Colors.RESET}{entry['user_id']}")
    if entry.get("conversation_id"):
        lines.append(f"{Colors.BRIGHT_CYAN}对话ID: {Colors.RESET}{entry['conversation_id']}")
    if entry.get("request_id"):
        lines.append(f"{Colors.BRIGHT_CYAN}请求ID: {Colors.RESET}{entry['request_id']}")

    # 调用位置
    if entry.get("filename"):
        lines.append(f"{Colors.DIM}位置: {entry['filename']}:{entry.get('lineno', '?')} in {entry.get('func_name', '?')}{Colors.RESET}")

    # 其他字段
    exclude_fields = {'timestamp', 'level', 'event', 'user_id', 'conversation_id', 'request_id',
                      'filename', 'lineno', 'func_name'}
    extra_fields = {k: v for k, v in entry.items() if k not in exclude_fields}

    if extra_fields:
        lines.append(f"\n{Colors.BRIGHT_CYAN}详细信息:{Colors.RESET}")
        for k, v in extra_fields.items():
            # 格式化值
            if isinstance(v, (dict, list)):
                v_str = json.dumps(v, indent=2, ensure_ascii=False)
            else:
                v_str = str(v)

            lines.append(f"  {Colors.GREEN}{k}:{Colors.RESET} {v_str}")

    lines.append(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")
    return "\n".join(lines)


def filter_entry(entry: Dict, filters: Dict) -> bool:
    """根据过滤条件判断是否显示该日志"""
    # 日志级别过滤
    if filters.get('level'):
        if entry.get('level', '').upper() != filters['level'].upper():
            return False

    # 用户过滤
    if filters.get('user_id'):
        if entry.get('user_id') != filters['user_id']:
            return False

    # 对话过滤
    if filters.get('conversation_id'):
        if entry.get('conversation_id') != filters['conversation_id']:
            return False

    # 关键词搜索
    if filters.get('search'):
        search_term = filters['search'].lower()
        # 在事件和所有字段值中搜索
        if search_term not in entry.get('event', '').lower():
            # 检查其他字段
            found = False
            for v in entry.values():
                if isinstance(v, str) and search_term in v.lower():
                    found = True
                    break
            if not found:
                return False

    return True


def view_logs(log_file: Path, filters: Dict, follow: bool = False, detailed: bool = False):
    """查看日志文件"""
    if not log_file.exists():
        print(f"{Colors.BRIGHT_RED}错误: 日志文件不存在: {log_file}{Colors.RESET}")
        return

    print(f"{Colors.BRIGHT_GREEN}正在读取日志: {log_file}{Colors.RESET}")
    if filters:
        print(f"{Colors.BRIGHT_YELLOW}过滤条件: {filters}{Colors.RESET}")
    print()

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            if follow:
                # 实时跟踪模式（类似 tail -f）
                # 先读取现有内容
                f.seek(0, 2)  # 跳到文件末尾
                print(f"{Colors.BRIGHT_CYAN}[实时跟踪模式，按 Ctrl+C 退出]{Colors.RESET}\n")

                while True:
                    line = f.readline()
                    if line:
                        entry = parse_log_line(line)
                        if entry and filter_entry(entry, filters):
                            if detailed:
                                print(format_detailed_entry(entry))
                            else:
                                print(format_log_entry(entry, show_full=True, highlight=filters.get('search')))
                    else:
                        time.sleep(0.1)  # 没有新内容，稍等
            else:
                # 普通模式
                count = 0
                for line in f:
                    entry = parse_log_line(line)
                    if entry and filter_entry(entry, filters):
                        if detailed:
                            print(format_detailed_entry(entry))
                        else:
                            print(format_log_entry(entry, show_full=detailed, highlight=filters.get('search')))
                        count += 1

                print(f"\n{Colors.BRIGHT_GREEN}共显示 {count} 条日志{Colors.RESET}")

    except KeyboardInterrupt:
        print(f"\n{Colors.BRIGHT_YELLOW}[已停止]{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.BRIGHT_RED}错误: {e}{Colors.RESET}")


def list_log_files(log_dir: Path):
    """列出所有日志文件"""
    if not log_dir.exists():
        print(f"{Colors.BRIGHT_RED}日志目录不存在: {log_dir}{Colors.RESET}")
        return

    log_files = sorted(log_dir.glob("app_*.log"), reverse=True)

    if not log_files:
        print(f"{Colors.BRIGHT_YELLOW}没有找到日志文件{Colors.RESET}")
        return

    print(f"{Colors.BRIGHT_GREEN}可用的日志文件:{Colors.RESET}\n")
    for log_file in log_files:
        size = log_file.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {Colors.CYAN}{log_file.name:<30}{Colors.RESET} {size_str:>10}  {Colors.DIM}修改: {mtime}{Colors.RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="日志查看工具 - 解析和美化显示结构化日志",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                              # 查看今天的日志
  %(prog)s --date 20251230              # 查看指定日期
  %(prog)s --user user_001              # 过滤特定用户
  %(prog)s --conversation conv_123      # 过滤特定对话
  %(prog)s --level ERROR                # 只看错误日志
  %(prog)s --follow                     # 实时跟踪
  %(prog)s --search "记忆"              # 搜索关键词
  %(prog)s --detailed                   # 显示详细信息
  %(prog)s --list                       # 列出所有日志文件
        """
    )

    parser.add_argument('--date', type=str, help='日期 (格式: YYYYMMDD)，默认今天')
    parser.add_argument('--log-dir', type=str, default='logs', help='日志目录路径')
    parser.add_argument('--user', type=str, help='过滤用户ID')
    parser.add_argument('--conversation', type=str, help='过滤对话ID')
    parser.add_argument('--level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='过滤日志级别')
    parser.add_argument('--search', type=str, help='搜索关键词')
    parser.add_argument('--follow', '-f', action='store_true', help='实时跟踪日志（类似 tail -f）')
    parser.add_argument('--detailed', '-d', action='store_true', help='显示详细信息')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有日志文件')
    parser.add_argument('--error', '-e', action='store_true', help='查看错误日志（快捷方式）')

    args = parser.parse_args()

    log_dir = Path(args.log_dir)

    # 列出日志文件
    if args.list:
        list_log_files(log_dir)
        return

    # 确定日志文件
    date_str = args.date or datetime.now().strftime("%Y%m%d")

    if args.error:
        log_file = log_dir / f"app_error_{date_str}.log"
    else:
        log_file = log_dir / f"app_{date_str}.log"

    # 构建过滤条件
    filters = {}
    if args.level:
        filters['level'] = args.level
    if args.user:
        filters['user_id'] = args.user
    if args.conversation:
        filters['conversation_id'] = args.conversation
    if args.search:
        filters['search'] = args.search

    # 查看日志
    view_logs(log_file, filters, follow=args.follow, detailed=args.detailed)


if __name__ == "__main__":
    main()
