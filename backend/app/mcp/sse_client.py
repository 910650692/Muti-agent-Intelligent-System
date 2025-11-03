"""SSE MCP Client: 连接通过HTTP SSE协议的MCP Server（如导航服务）"""
import httpx
import json
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import uuid


class SSEMCPClient:
    """SSE MCP 客户端，通过HTTP SSE连接MCP Server（如导航服务）

    实现标准MCP HTTP+SSE协议 (2024-11-05):
    1. GET /sse 建立SSE长连接，获取sessionId
    2. POST /message?sessionId=xxx 发送JSON-RPC请求（返回202 Accepted）
    3. 通过SSE stream接收JSON-RPC响应（message事件）
    """

    def __init__(self, server_name: str):
        """
        Args:
            server_name: MCP Server 的标识名称
        """
        self.server_name = server_name
        self.base_url: Optional[str] = None
        self.session_id: Optional[str] = None
        self.message_url: Optional[str] = None
        self.tools: List[Any] = []
        self.client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

        # SSE连接管理
        self._sse_task: Optional[asyncio.Task] = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._pending_requests: Dict[int, asyncio.Future] = {}

    @asynccontextmanager
    async def connect(self, url: str):
        """
        连接到 SSE MCP Server

        Args:
            url: MCP Server 的 SSE endpoint URL (如 http://localhost:8080/sse)
        """
        self.base_url = url
        # SSE长连接需要禁用读取超时，但保留连接超时
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,   # 连接超时10秒
                read=None,      # 读取超时禁用（SSE需要长连接）
                write=10.0,     # 写入超时10秒
                pool=10.0       # 连接池超时10秒
            )
        )

        print(f"[SSE MCP Client] [{self.server_name}] 正在连接: {url}")

        try:
            # 启动SSE监听任务
            self._sse_task = asyncio.create_task(self._sse_listener(url))

            # 等待获取endpoint
            try:
                await asyncio.wait_for(self._wait_for_endpoint(), timeout=5.0)
            except asyncio.TimeoutError:
                raise Exception("等待endpoint事件超时")

            if not self.session_id:
                raise Exception("未能获取sessionId")

            print(f"[SSE MCP Client] [{self.server_name}] Session ID: {self.session_id}")
            print(f"[SSE MCP Client] [{self.server_name}] Message URL: {self.message_url}")

            # 2. 初始化MCP连接
            print(f"[SSE MCP Client] [{self.server_name}] 发送initialize请求...")
            init_result = await self._call_method("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "python-mcp-client",
                    "version": "1.0.0"
                }
            })

            print(f"[SSE MCP Client] [{self.server_name}] 初始化成功")

            # 3. 获取工具列表
            print(f"[SSE MCP Client] [{self.server_name}] 获取工具列表...")
            tools_result = await self._call_method("tools/list", {})

            # 解析工具列表
            if "tools" in tools_result:
                self.tools = tools_result["tools"]
            elif isinstance(tools_result, list):
                self.tools = tools_result
            else:
                self.tools = []

            print(f"[SSE MCP Client] [{self.server_name}] 连接成功！")
            print(f"[SSE MCP Client] [{self.server_name}] 可用工具 ({len(self.tools)}):")
            for tool in self.tools:
                if isinstance(tool, dict):
                    tool_name = tool.get("name", "unknown")
                    tool_desc = tool.get("description", "")
                    print(f"  - {tool_name}: {tool_desc[:60]}...")
                else:
                    print(f"  - {tool}")

            yield self

        except Exception as e:
            print(f"[SSE MCP Client] [{self.server_name}] 连接失败: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # 取消SSE监听任务
            if self._sse_task:
                self._sse_task.cancel()
                try:
                    await self._sse_task
                except asyncio.CancelledError:
                    pass

            if self.client:
                await self.client.aclose()

    async def _wait_for_endpoint(self):
        """等待从SSE获取endpoint"""
        while not self.session_id:
            await asyncio.sleep(0.1)

    async def _sse_listener(self, url: str):
        """
        SSE监听任务：保持连接打开，持续接收服务器消息
        """
        try:
            async with self.client.stream("GET", url) as response:
                print(f"[SSE MCP Client] [{self.server_name}] SSE连接已建立: {response.status_code}")

                if response.status_code != 200:
                    raise Exception(f"SSE连接失败: HTTP {response.status_code}")

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk

                    # 解析SSE事件（支持\r\n\r\n或\n\n分隔符）
                    separator = "\r\n\r\n" if "\r\n\r\n" in buffer else "\n\n"

                    while separator in buffer:
                        event_block, buffer = buffer.split(separator, 1)
                        await self._handle_sse_event(event_block)

        except asyncio.CancelledError:
            print(f"[SSE MCP Client] [{self.server_name}] SSE监听任务已取消")
            raise
        except Exception as e:
            print(f"[SSE MCP Client] [{self.server_name}] SSE监听错误: {e}")
            import traceback
            traceback.print_exc()

    async def _handle_sse_event(self, event_block: str):
        """
        处理单个SSE事件
        """
        # 解析事件（兼容data在前或event在前的情况）
        event_type = None
        event_data = None

        # 支持\r\n和\n两种换行符
        lines = event_block.replace("\r\n", "\n").split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                event_data = line[5:].strip()

        print(f"[SSE MCP Client] [{self.server_name}] 收到事件: type={event_type}, data={event_data[:100] if event_data else None}...")

        # 处理endpoint事件（第一个事件）
        if event_type == "endpoint" and event_data:
            if "sessionId=" in event_data:
                self.session_id = event_data.split("sessionId=")[1]
                # 构建完整的message URL
                base = self.base_url.rsplit("/", 1)[0]  # 去掉/sse
                self.message_url = f"{base}{event_data}"

        # 处理message事件（JSON-RPC响应）
        elif event_type == "message" and event_data:
            try:
                message = json.loads(event_data)

                # 如果是响应（有id字段），匹配到对应的请求
                if "id" in message:
                    request_id = message["id"]
                    print(f"[SSE MCP Client] [{self.server_name}] 收到响应 id={request_id}, 待处理请求={list(self._pending_requests.keys())}")

                    if request_id in self._pending_requests:
                        future = self._pending_requests.pop(request_id)

                        if "error" in message:
                            future.set_exception(Exception(f"MCP Error: {message['error']}"))
                        else:
                            future.set_result(message.get("result", {}))
                    else:
                        # 服务器主动发送的通知/请求，或者是旧的响应
                        print(f"[SSE MCP Client] [{self.server_name}] 收到未匹配的消息 id={request_id}: {message}")
                else:
                    # 没有id的通知
                    print(f"[SSE MCP Client] [{self.server_name}] 收到服务器通知: {message}")

            except json.JSONDecodeError as e:
                print(f"[SSE MCP Client] [{self.server_name}] JSON解析错误: {e}, data: {event_data}")

    async def _call_method(self, method: str, params: Dict[str, Any]) -> Any:
        """
        调用 MCP JSON-RPC 方法

        Args:
            method: 方法名（如 "initialize", "tools/list", "tools/call"）
            params: 方法参数

        Returns:
            方法执行结果
        """
        if not self.client or not self.message_url:
            raise Exception(f"[{self.server_name}] MCP 会话未建立")

        # 检查SSE监听任务状态
        if self._sse_task and self._sse_task.done():
            print(f"[SSE MCP Client] [{self.server_name}] 警告: SSE监听任务已停止！")
            if self._sse_task.exception():
                print(f"[SSE MCP Client] [{self.server_name}] SSE任务异常: {self._sse_task.exception()}")

        # 生成唯一的请求ID
        self._request_id += 1
        request_id = self._request_id

        # 构造 JSON-RPC 请求
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }

        # 创建Future等待响应
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        print(f"[SSE MCP Client] [{self.server_name}] 调用方法: {method} (id={request_id})")
        print(f"[SSE MCP Client] [{self.server_name}] 当前待处理请求: {list(self._pending_requests.keys())}")

        try:
            # 发送 HTTP POST 请求到 /message?sessionId=xxx
            response = await self.client.post(
                self.message_url,
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

            print(f"[SSE MCP Client] [{self.server_name}] POST响应: {response.status_code}")

            # 期望返回 202 Accepted
            if response.status_code == 202:
                # 等待从SSE接收响应
                print(f"[SSE MCP Client] [{self.server_name}] 等待SSE响应 (id={request_id}, timeout=30s)...")
                result = await asyncio.wait_for(future, timeout=30.0)
                print(f"[SSE MCP Client] [{self.server_name}] 收到响应 (id={request_id})")
                return result
            else:
                # 如果不是202，可能是错误
                raise Exception(f"POST请求失败: HTTP {response.status_code}, body: {response.text}")

        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            print(f"[SSE MCP Client] [{self.server_name}] 等待响应超时 (id={request_id})")
            print(f"[SSE MCP Client] [{self.server_name}] 剩余待处理请求: {list(self._pending_requests.keys())}")
            raise Exception(f"等待响应超时: {method} (id={request_id})")
        except Exception as e:
            self._pending_requests.pop(request_id, None)
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
        print(f"[SSE MCP Client] [{self.server_name}] 调用工具: {tool_name}")
        print(f"[SSE MCP Client] [{self.server_name}] 参数: {arguments}")

        # 调用 tools/call 方法
        result = await self._call_method("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

        print(f"[SSE MCP Client] [{self.server_name}] 工具返回: {result}")

        return result
