"""
mcp_server.py - 共享 MCP Server 核心
=====================================

ArtClaw 统一 MCP Server 实现，供所有 DCC 插件使用。
支持 WebSocket + HTTP 双通道，工具注册，权限控制。
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("artclaw.mcp")


@dataclass
class ToolDefinition:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    main_thread: bool = False  # 是否需要主线程执行


@dataclass
class ToolCall:
    """工具调用请求"""
    name: str
    arguments: Dict[str, Any]
    call_id: str


@dataclass
class ToolResult:
    """工具调用结果"""
    call_id: str
    success: bool
    content: List[Dict[str, Any]]
    is_error: bool = False
    error_message: Optional[str] = None
    duration_ms: float = 0


class MCPServer:
    """
    ArtClaw MCP Server（WebSocket 模式）。

    使用示例：
        def my_handler(args) -> dict:
            return {"content": [{"type": "text", "text": "hello"}]}

        server = MCPServer(host="127.0.0.1", port=8088)
        server.register_tool(
            name="my_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            handler=my_handler,
        )
        server.start()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8088):
        self.host = host
        self.port = port
        self._tools: Dict[str, ToolDefinition] = {}
        self._running = False
        self._start_time = time.time()

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable,
        main_thread: bool = False,
    ) -> None:
        """注册一个 MCP 工具"""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
            main_thread=main_thread,
        )
        logger.info(f"注册工具: {name}")

    def get_tools(self) -> List[Dict[str, Any]]:
        """返回所有已注册工具的元信息"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    async def handle_tool_call(self, call: ToolCall) -> ToolResult:
        """执行工具调用"""
        start = time.time()
        tool = self._tools.get(call.name)

        if not tool:
            return ToolResult(
                call_id=call.call_id,
                success=False,
                content=[],
                is_error=True,
                error_message=f"未知工具: {call.name}",
                duration_ms=(time.time() - start) * 1000,
            )

        try:
            # 同步 handler 包装
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(call.arguments)
            else:
                result = tool.handler(call.arguments)

            # 标准化返回值
            if isinstance(result, dict):
                content = result.get("content", [])
                is_error = result.get("isError", False)
                error_msg = result.get("error")
            else:
                content = [{"type": "text", "text": str(result)}]
                is_error = False
                error_msg = None

            return ToolResult(
                call_id=call.call_id,
                success=not is_error,
                content=content,
                is_error=is_error,
                error_message=error_msg,
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            logger.error(f"工具 {call.name} 执行异常: {e}")
            return ToolResult(
                call_id=call.call_id,
                success=False,
                content=[],
                is_error=True,
                error_message=str(e),
                duration_ms=(time.time() - start) * 1000,
            )

    def start(self) -> None:
        """启动服务器（同步入口，调用 asyncio.run）"""
        asyncio.run(self._run())

    async def run_stdio(self) -> None:
        """stdio 模式：读取 stdin，输出 stdout（供 mcporter 等工具使用）"""
        self._running = True
        logger.info("MCP Server stdio 模式就绪")
        loop = asyncio.get_event_loop()
        reader = asyncio.create_task(loop.run_interno(self._read_stdio))

        async def read_loop():
            try:
                while self._running:
                    line = await asyncio.wait_for(loop.run_interno(sys.stdin.readline), timeout=1.0)
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        req = json.loads(line)
                        resp = await self._process_message(req)
                        if resp:
                            print(json.dumps(resp), flush=True)
                    except json.JSONDecodeError:
                        print(json.dumps({
                            "jsonrpc": "2.0",
                            "error": {"code": -32700, "message": "Parse error"},
                        }), flush=True)
                    except Exception as e:
                        print(json.dumps({
                            "jsonrpc": "2.0",
                            "error": {"code": -32603, "message": str(e)},
                        }), flush=True)
            except asyncio.TimeoutError:
                pass  # 继续循环检查 _running

        try:
            await read_loop()
        except KeyboardInterrupt:
            self._running = False

    async def _read_stdio(self) -> str:
        return sys.stdin.readline()

    async def _run(self) -> None:
        """主运行循环"""
        self._running = True
        logger.info(f"MCP Server 启动 ws://{self.host}:{self.port}")

        try:
            import websockets
        except ImportError:
            logger.error("缺少依赖: pip install websockets")
            return

        async with websockets.serve(self._handle_client, self.host, self.port):
            await asyncio.Future()  # 永久运行

    async def _handle_client(self, websocket) -> None:
        """处理 WebSocket 客户端连接"""
        client_id = str(uuid.uuid4())[:8]
        logger.info(f"客户端连接: {client_id} from {websocket.remote_address}")

        try:
            async for message in websocket:
                try:
                    req = json.loads(message)
                    resp = await self._process_message(req)
                    if resp:
                        await websocket.send(json.dumps(resp))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                    }))
                except Exception as e:
                    logger.error(f"处理消息异常: {e}")
                    await websocket.send(json.dumps({
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": str(e)},
                    }))
        except Exception as e:
            logger.warning(f"客户端 {client_id} 断开: {e}")

    async def _process_message(self, req: Dict) -> Optional[Dict]:
        """处理 MCP JSON-RPC 请求"""
        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "artclaw-mcp-server", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                },
            }

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.get_tools()},
            }

        if method == "tools/call":
            params = req.get("params", {})
            result = await self.handle_tool_call(ToolCall(
                name=params.get("name", ""),
                arguments=params.get("arguments", {}),
                call_id=str(uuid.uuid4()),
            ))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": result.content, "isError": result.is_error},
            }

        if method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"status": "ok", "uptime": time.time() - self._start_time},
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def format_tool_result(text: str, is_error: bool = False) -> Dict:
    """标准化工具返回结果"""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def format_json_result(data: Any) -> Dict:
    """JSON 序列化工具返回结果"""
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}
