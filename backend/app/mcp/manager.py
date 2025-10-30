"""MCP Manager: 管理多个 MCP Server 和工具加载"""
import asyncio
import threading
from typing import Dict, List, Any, Callable, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from .client import MCPClient
from .config import get_enabled_servers


class MCPManager:
    """MCP 管理器：管理多个 MCP Server，动态加载工具"""

    def __init__(self):
        """初始化 MCP Manager"""
        self.servers = get_enabled_servers()
        self._tools_cache: Optional[List[StructuredTool]] = None  # 工具缓存
        self._cache_lock = threading.Lock()  # 线程锁

        print(f"[MCP Manager] 初始化完成，已注册 {len(self.servers)} 个 MCP Server")
        for name, config in self.servers.items():
            print(f"  - {name}: {config['description']}")

    async def load_all_tools_async(self) -> List[StructuredTool]:
        """
        异步加载所有启用的 MCP Server 的工具，并转换为 LangChain StructuredTool

        Returns:
            LangChain StructuredTool 列表
        """
        all_tools = []

        for server_name, server_config in self.servers.items():
            print(f"\n[MCP Manager] 正在加载 {server_name} 的工具...")

            try:
                client = MCPClient(server_name)

                async with client.connect(
                    command=server_config["command"],
                    args=server_config["args"],
                    env=server_config.get("env")  # 使用 get，env 是可选的
                ):
                    # 遍历该 Server 的所有工具
                    for mcp_tool in client.tools:
                        # 为每个 MCP 工具创建对应的 LangChain Tool
                        langchain_tool = self._create_langchain_tool(
                            server_name=server_name,
                            server_config=server_config,
                            mcp_tool=mcp_tool
                        )
                        all_tools.append(langchain_tool)

                print(f"[MCP Manager] {server_name} 加载完成，共 {len(client.tools)} 个工具")

            except Exception as e:
                print(f"[MCP Manager] 加载 {server_name} 失败: {e}")
                import traceback
                traceback.print_exc()
                # 继续加载其他 Server

        print(f"\n[MCP Manager] 所有工具加载完成，共 {len(all_tools)} 个工具")
        return all_tools

    def load_all_tools(self, use_cache: bool = True) -> List[StructuredTool]:
        """
        同步加载所有工具（包装异步方法，带缓存）

        Args:
            use_cache: 是否使用缓存（默认 True）

        Returns:
            LangChain StructuredTool 列表
        """
        # 如果使用缓存且缓存存在，直接返回
        if use_cache and self._tools_cache is not None:
            print(f"[MCP Manager] 使用缓存的工具列表，共 {len(self._tools_cache)} 个工具")
            return self._tools_cache

        with self._cache_lock:
            # 双重检查锁定模式
            if use_cache and self._tools_cache is not None:
                return self._tools_cache

            # 在新线程中运行异步代码
            import concurrent.futures

            def run_async_in_thread():
                """在新线程中运行异步代码"""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.load_all_tools_async())
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async_in_thread)
                tools = future.result(timeout=60)  # 60秒超时

            # 缓存工具列表
            if use_cache:
                self._tools_cache = tools

            return tools

    def clear_cache(self):
        """清除工具缓存"""
        with self._cache_lock:
            self._tools_cache = None
            print("[MCP Manager] 工具缓存已清除")

    def _create_langchain_tool(
        self,
        server_name: str,
        server_config: Dict[str, Any],
        mcp_tool: Any
    ) -> StructuredTool:
        """
        将 MCP 工具转换为 LangChain StructuredTool

        Args:
            server_name: MCP Server 名称
            server_config: MCP Server 配置
            mcp_tool: MCP 工具对象

        Returns:
            LangChain StructuredTool
        """
        # 从 MCP 工具的 inputSchema 动态创建 Pydantic 模型
        input_schema = mcp_tool.inputSchema

        # 构建 Pydantic 字段
        fields = {}
        if input_schema and 'properties' in input_schema:
            required_fields = input_schema.get('required', [])

            for param_name, param_schema in input_schema['properties'].items():
                param_type = param_schema.get('type', 'string')
                param_desc = param_schema.get('description', '')

                # 映射 JSON Schema 类型到 Python 类型
                python_type = {
                    'string': str,
                    'integer': int,
                    'number': float,
                    'boolean': bool,
                    'array': list,
                    'object': dict,
                }.get(param_type, str)

                # 判断是否必填
                is_required = param_name in required_fields

                if is_required:
                    fields[param_name] = (python_type, Field(description=param_desc))
                else:
                    fields[param_name] = (python_type, Field(default=None, description=param_desc))

        # 动态创建 Pydantic 模型
        ArgsModel = create_model(
            f"{mcp_tool.name}_args",
            **fields
        ) if fields else None

        # 创建工具函数
        def tool_func(**kwargs) -> str:
            """实际执行 MCP 工具的函数"""
            print(f"[Tool] 调用 {mcp_tool.name}，参数: {kwargs}")

            async def call_mcp():
                client = MCPClient(server_name)
                async with client.connect(
                    command=server_config["command"],
                    args=server_config["args"],
                    env=server_config.get("env")
                ):
                    result = await client.call_tool(mcp_tool.name, kwargs)
                    return client.extract_result_text(result)

            # 在新线程中运行异步函数
            import concurrent.futures

            def run_in_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(call_mcp())
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=30)

        # 工具名称：避免重名，加上 server 前缀
        tool_name = f"{server_name}_{mcp_tool.name}" if len(self.servers) > 1 else mcp_tool.name

        # 工具描述：加上来源说明
        tool_description = f"[{server_name}] {mcp_tool.description}"

        # 创建 StructuredTool
        if ArgsModel:
            return StructuredTool.from_function(
                func=tool_func,
                name=tool_name,
                description=tool_description,
                args_schema=ArgsModel
            )
        else:
            # 如果没有参数schema，使用简单的Tool
            return StructuredTool.from_function(
                func=tool_func,
                name=tool_name,
                description=tool_description
            )

    async def get_all_tools_schema_async(self) -> List[Dict[str, Any]]:
        """
        异步获取所有工具的 Schema（用于直接传递给 LLM）

        Returns:
            工具 Schema 列表
        """
        all_schemas = []

        for server_name, server_config in self.servers.items():
            try:
                client = MCPClient(server_name)

                async with client.connect(
                    command=server_config["command"],
                    args=server_config["args"],
                    env=server_config.get("env")  # 使用 get，env 是可选的
                ):
                    schemas = client.get_tools_schema()
                    # 添加 server 信息
                    for schema in schemas:
                        schema["server"] = server_name
                    all_schemas.extend(schemas)

            except Exception as e:
                print(f"[MCP Manager] 获取 {server_name} schema 失败: {e}")

        return all_schemas

    def get_all_tools_schema(self) -> List[Dict[str, Any]]:
        """
        同步获取所有工具的 Schema

        Returns:
            工具 Schema 列表
        """
        return asyncio.run(self.get_all_tools_schema_async())

    def register_server(
        self,
        name: str,
        command: str,
        args: List[str],
        env: Dict[str, str] = None,
        description: str = "",
        enabled: bool = True
    ):
        """
        动态注册新的 MCP Server

        Args:
            name: Server 名称
            command: 启动命令
            args: 命令参数
            env: 环境变量
            description: 描述
            enabled: 是否启用
        """
        self.servers[name] = {
            "command": command,
            "args": args,
            "env": env,
            "description": description,
            "enabled": enabled
        }
        print(f"[MCP Manager] 已注册 Server: {name}")

    def unregister_server(self, name: str):
        """
        注销 MCP Server

        Args:
            name: Server 名称
        """
        if name in self.servers:
            del self.servers[name]
            print(f"[MCP Manager] 已注销 Server: {name}")


# 全局单例 MCP Manager
mcp_manager = MCPManager()
