"""通用 MCP Client: 可以连接任何 MCP Server"""
import os
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """通用 MCP 客户端，可连接任何 MCP Server"""

    def __init__(self, server_name: str):
        """
        Args:
            server_name: MCP Server 的标识名称（用于日志和区分）
        """
        self.server_name = server_name
        self.session: Optional[ClientSession] = None
        self.tools: List[Any] = []

    @asynccontextmanager
    async def connect(self, command: str, args: List[str] = None, env: Dict[str, str] = None):
        """
        连接到 MCP Server

        Args:
            command: 启动命令（如 "npx", "python", "node"）
            args: 命令参数（如 ["-y", "duckduckgo-mcp-server"]）
            env: 环境变量（默认使用当前环境变量）
        """
        server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env or os.environ.copy()
        )

        print(f"[MCP Client] [{self.server_name}] 正在连接...")
        print(f"[MCP Client] [{self.server_name}] 命令: {command} {' '.join(args or [])}")

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session

                    # 初始化会话
                    await session.initialize()

                    # 获取可用工具列表
                    tools_result = await session.list_tools()
                    self.tools = tools_result.tools

                    print(f"[MCP Client] [{self.server_name}] 连接成功！")
                    print(f"[MCP Client] [{self.server_name}] 可用工具 ({len(self.tools)}):")
                    for tool in self.tools:
                        print(f"  - {tool.name}: {tool.description}")

                    yield self
        except Exception as e:
            print(f"[MCP Client] [{self.server_name}] 连接失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        调用 MCP 工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        if not self.session:
            raise Exception(f"[{self.server_name}] MCP 会话未建立")

        print(f"[MCP Client] [{self.server_name}] 调用工具: {tool_name}")
        print(f"[MCP Client] [{self.server_name}] 参数: {arguments}")

        try:
            result = await self.session.call_tool(tool_name, arguments)
            print(f"[MCP Client] [{self.server_name}] 调用成功")
            return result
        except Exception as e:
            print(f"[MCP Client] [{self.server_name}] 调用失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的 Schema（用于传递给 LLM）

        Returns:
            工具 Schema 列表
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            for tool in self.tools
        ]

    def extract_result_text(self, result: Any) -> str:
        """
        从 MCP 工具返回结果中提取文本

        Args:
            result: MCP 工具返回的结果对象

        Returns:
            提取的文本内容
        """
        if not result or not hasattr(result, 'content'):
            return "无返回结果"

        text_parts = []
        for item in result.content:
            if hasattr(item, 'text'):
                text_parts.append(item.text)
            else:
                text_parts.append(str(item))

        return "\n\n".join(text_parts) if text_parts else "无返回内容"
