"""MCP Manager: 管理多个 MCP Server 和工具加载"""
import asyncio
import threading
from typing import Dict, List, Any, Callable, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from .client import MCPClient
from .sse_client import SSEMCPClient
from .config import get_enabled_servers


class MCPManager:
    """MCP 管理器：管理多个 MCP Server，动态加载工具"""

    def __init__(self):
        """初始化 MCP Manager"""
        self.servers = get_enabled_servers()
        self._tools_cache: Optional[List[StructuredTool]] = None  # 工具缓存
        self._cache_lock = threading.Lock()  # 线程锁

        # SSE客户端连接池（保持长连接）
        self._sse_clients: Dict[str, SSEMCPClient] = {}
        self._sse_connections: Dict[str, Any] = {}  # 存储连接上下文
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None  # 主事件循环
        self._loop_thread: Optional[threading.Thread] = None  # 事件循环线程

        print(f"[MCP Manager] 初始化完成，已注册 {len(self.servers)} 个 MCP Server")
        for name, config in self.servers.items():
            print(f"  - {name}: {config['description']}")

    def _start_event_loop(self):
        """在后台线程中启动event loop"""
        self._main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._main_loop)
        print("[MCP Manager] Event loop 线程已启动")
        self._main_loop.run_forever()
        print("[MCP Manager] Event loop 线程已停止")

    def _ensure_event_loop(self):
        """确保event loop线程正在运行"""
        if self._loop_thread is None or not self._loop_thread.is_alive():
            self._loop_thread = threading.Thread(target=self._start_event_loop, daemon=True)
            self._loop_thread.start()
            # 等待loop启动
            import time
            while self._main_loop is None:
                time.sleep(0.01)

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
                # ✅ 判断 transport 类型
                transport = server_config.get("transport", "stdio")

                if transport == "sse":
                    # SSE transport (HTTP连接，如导航服务) - 建立长连接
                    client = SSEMCPClient(server_name)
                    url = server_config.get("url")

                    if not url:
                        print(f"[MCP Manager] {server_name} 缺少url配置，跳过")
                        continue

                    # 建立连接并保存到连接池
                    print(f"[MCP Manager] 正在为 {server_name} 建立长连接...")
                    conn = client.connect(url=url)
                    await conn.__aenter__()  # 进入异步上下文

                    # 保存客户端和连接上下文
                    self._sse_clients[server_name] = client
                    self._sse_connections[server_name] = conn

                    # 遍历该 Server 的所有工具
                    for mcp_tool in client.tools:
                        # 为每个 MCP 工具创建对应的 LangChain Tool
                        langchain_tool = self._create_langchain_tool_sse(
                            server_name=server_name,
                            server_config=server_config,
                            mcp_tool=mcp_tool
                        )
                        all_tools.append(langchain_tool)

                    print(f"[MCP Manager] {server_name} 长连接建立完成，共 {len(client.tools)} 个工具")

                else:
                    # stdio transport (命令行启动，如12306、搜索服务)
                    client = MCPClient(server_name)

                    async with client.connect(
                        command=server_config["command"],
                        args=server_config["args"],
                        env=server_config.get("env")
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

            # 确保event loop线程运行
            self._ensure_event_loop()

            # 在持久的event loop中运行异步代码
            future = asyncio.run_coroutine_threadsafe(
                self.load_all_tools_async(),
                self._main_loop
            )
            tools = future.result(timeout=60)

            # 缓存工具列表
            if use_cache:
                self._tools_cache = tools

            return tools

    def clear_cache(self):
        """清除工具缓存"""
        with self._cache_lock:
            self._tools_cache = None
            print("[MCP Manager] 工具缓存已清除")

    async def cleanup_async(self):
        """异步清理所有SSE连接"""
        print("[MCP Manager] 正在关闭所有SSE连接...")
        for server_name, conn in self._sse_connections.items():
            try:
                await conn.__aexit__(None, None, None)
                print(f"[MCP Manager] {server_name} 连接已关闭")
            except Exception as e:
                print(f"[MCP Manager] 关闭 {server_name} 连接失败: {e}")

        self._sse_clients.clear()
        self._sse_connections.clear()

    def cleanup(self):
        """同步清理所有SSE连接"""
        if not self._sse_connections:
            return

        if self._main_loop and self._main_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.cleanup_async(), self._main_loop)
            future.result(timeout=10)

        # 停止event loop
        if self._main_loop:
            self._main_loop.call_soon_threadsafe(self._main_loop.stop)
        if self._loop_thread:
            self._loop_thread.join(timeout=5)

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

    def _create_langchain_tool_sse(
        self,
        server_name: str,
        server_config: Dict[str, Any],
        mcp_tool: Any
    ) -> StructuredTool:
        """
        将 SSE MCP 工具转换为 LangChain StructuredTool

        Args:
            server_name: MCP Server 名称
            server_config: MCP Server 配置
            mcp_tool: MCP 工具对象（dict格式）

        Returns:
            LangChain StructuredTool
        """
        # SSE工具是dict格式，需要适配
        if isinstance(mcp_tool, dict):
            tool_name_raw = mcp_tool.get("name", "unknown")
            tool_description_raw = mcp_tool.get("description", "")
            input_schema = mcp_tool.get("inputSchema", {})
        else:
            # 兼容对象格式
            tool_name_raw = mcp_tool.name
            tool_description_raw = mcp_tool.description
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
            f"{tool_name_raw}_args",
            **fields
        ) if fields else None

        # 创建工具函数（SSE版本 - 复用连接）
        def tool_func(**kwargs) -> str:
            """实际执行 SSE MCP 工具的函数（使用连接池）"""
            print(f"[Tool] 调用 {tool_name_raw}，参数: {kwargs}")

            async def call_mcp():
                # 从连接池获取已建立的客户端
                client = self._sse_clients.get(server_name)
                if not client:
                    raise Exception(f"SSE客户端 {server_name} 未连接")

                # 直接调用工具，无需重新连接
                result = await client.call_tool(tool_name_raw, kwargs)

                # 提取结果文本
                if isinstance(result, dict):
                    # 处理MCP工具返回的格式
                    if "content" in result:
                        content = result["content"]
                        if isinstance(content, list) and len(content) > 0:
                            return content[0].get("text", str(result))
                        return str(content)
                    return str(result)
                return str(result)

            # 使用保存的主event loop执行
            if self._main_loop and self._main_loop.is_running():
                # 在主loop中异步执行，并在当前线程中等待
                future = asyncio.run_coroutine_threadsafe(call_mcp(), self._main_loop)
                return future.result(timeout=30)
            else:
                # 如果主loop不可用，创建新的loop
                return asyncio.run(call_mcp())

        # 工具名称：避免重名，加上 server 前缀
        tool_name = f"{server_name}_{tool_name_raw}" if len(self.servers) > 1 else tool_name_raw

        # 工具描述：加上来源说明
        tool_description = f"[{server_name}] {tool_description_raw}"

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
