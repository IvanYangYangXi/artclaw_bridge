"""
mcp_server.py - DCCClawBridge MCP WebSocket 服务器
====================================================

从 UEClawBridge 的 mcp_server.py 移植，适配 DCC (Maya/Max) 环境。

核心区别:
  - UE: Slate tick 驱动 asyncio 事件循环（_UEAsyncBridge）
  - DCC: 独立线程运行 asyncio 事件循环 + QTimer 跨线程回调主线程

架构:
  MCP Server (asyncio 线程) ←WebSocket→ mcp-bridge 插件 (OpenClaw Gateway)
  MCP Server 收到 tools/call → command_queue → 主线程执行 → 返回结果
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
import time
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger("artclaw.mcp")

# --- 常量 ---

JSONRPC_VERSION = "2.0"
MCP_VERSION = "2024-11-05"
SERVER_NAME = "artclaw-dcc-bridge"
SERVER_VERSION = "0.1.0"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8081  # UE 用 8080，DCC 从 8081 开始
MAX_PORT_PROBE = 10

WS_PING_INTERVAL = 30
WS_PING_TIMEOUT = 10

# JSON-RPC 错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

# --- websockets 可用性检查 ---

_HAS_WEBSOCKETS = False
try:
    from websockets.server import serve as ws_serve
    from websockets.exceptions import ConnectionClosed
    _HAS_WEBSOCKETS = True
except ImportError:
    pass


# --- JSON-RPC 辅助 ---

def _make_jsonrpc_response(request_id: Any, result: Any) -> str:
    return json.dumps({
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "result": result,
    }, default=str, ensure_ascii=False)


def _make_jsonrpc_error(request_id: Any, code: int, message: str, data: Any = None) -> str:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return json.dumps({
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": error,
    }, default=str, ensure_ascii=False)


# --- MCPServer ---

class MCPServer:
    """
    MCP WebSocket 通信服务器 (DCC 版本)。

    在独立线程中运行 asyncio 事件循环。
    工具调用通过 command_queue 转发到 DCC 主线程执行。
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._host = host
        self._port = port
        self._actual_port: Optional[int] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        self._thread: Optional[threading.Thread] = None

        self._clients: Set = set()
        self._initialized_clients: Set[int] = set()

        self._running = False

        # Tool 注册表
        self._tools: Dict[str, dict] = {}

        # 主线程执行器（由外部注入，如 adapter.execute_on_main_thread）
        self._main_thread_executor: Optional[Callable] = None

    # --- 属性 ---

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def actual_port(self) -> Optional[int]:
        return self._actual_port

    @property
    def server_address(self) -> str:
        if self._actual_port:
            return f"ws://{self._host}:{self._actual_port}"
        return ""

    # --- 端口探测 ---

    @staticmethod
    def _is_port_available(host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.bind((host, port))
                return True
        except OSError:
            return False

    def _find_available_port(self) -> int:
        for offset in range(MAX_PORT_PROBE):
            candidate = self._port + offset
            if self._is_port_available(self._host, candidate):
                if offset > 0:
                    logger.info(f"Port {self._port} occupied, using {candidate}")
                return candidate
        logger.warning(f"All ports {self._port}-{self._port + MAX_PORT_PROBE} occupied")
        return self._port

    # --- WebSocket 连接处理 ---

    async def _connection_handler(self, websocket):
        client_id = id(websocket)
        self._clients.add(websocket)
        logger.info(f"MCP client connected (total: {len(self._clients)})")

        try:
            async for raw_message in websocket:
                try:
                    response = await self._handle_message(websocket, raw_message)
                    if response:
                        await websocket.send(response)
                except Exception as e:
                    logger.error(f"Message handling error: {e}")
                    try:
                        await websocket.send(
                            _make_jsonrpc_error(None, INTERNAL_ERROR, str(e))
                        )
                    except Exception:
                        pass

        except ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            self._clients.discard(websocket)
            self._initialized_clients.discard(client_id)
            logger.info(f"MCP client disconnected (remaining: {len(self._clients)})")

    # --- MCP 消息路由 ---

    async def _handle_message(self, websocket, raw_message: str) -> Optional[str]:
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError as e:
            return _make_jsonrpc_error(None, PARSE_ERROR, f"JSON parse error: {e}")

        if not isinstance(msg, dict) or msg.get("jsonrpc") != JSONRPC_VERSION:
            return _make_jsonrpc_error(msg.get("id"), INVALID_REQUEST, "Invalid JSON-RPC 2.0")

        method = msg.get("method", "")
        params = msg.get("params", {})
        request_id = msg.get("id")

        handlers = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
        }

        handler = handlers.get(method)
        if handler is None:
            if request_id is not None:
                return _make_jsonrpc_error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")
            return None

        try:
            result = await handler(websocket, params)
            if request_id is not None:
                return _make_jsonrpc_response(request_id, result)
            return None
        except Exception as e:
            logger.error(f"Handler error for {method}: {e}")
            if request_id is not None:
                return _make_jsonrpc_error(request_id, INTERNAL_ERROR, str(e))
            return None

    # --- MCP 协议方法 ---

    async def _handle_initialize(self, websocket, params: dict) -> dict:
        client_info = params.get("clientInfo", {})
        logger.info(f"MCP initialize from {client_info.get('name', 'unknown')}")
        return {
            "protocolVersion": MCP_VERSION,
            "capabilities": {
                "tools": {"listChanged": True},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        }

    async def _handle_initialized(self, websocket, params: dict) -> None:
        self._initialized_clients.add(id(websocket))
        logger.info("MCP client initialized")

    async def _handle_ping(self, websocket, params: dict) -> dict:
        return {}

    async def _handle_tools_list(self, websocket, params: dict) -> dict:
        tools = []
        for tool in self._tools.values():
            tools.append({k: v for k, v in tool.items() if not k.startswith("_")})
        logger.info(f"tools/list -> {len(tools)} tools")
        return {"tools": tools}

    async def _handle_tools_call(self, websocket, params: dict) -> dict:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        logger.info(f"tools/call -> {tool_name}")

        tool_def = self._tools[tool_name]
        handler = tool_def.get("_handler")
        if handler is None:
            raise ValueError(f"Tool '{tool_name}' has no handler")

        try:
            # 如果设置了主线程执行器且 handler 需要主线程，在主线程执行
            if tool_def.get("_main_thread", False) and self._main_thread_executor:
                result = await self._execute_on_main_thread(handler, arguments)
            elif asyncio.iscoroutinefunction(handler):
                result = await handler(arguments)
            else:
                result = handler(arguments)

            # 标准化结果
            if isinstance(result, dict) and "content" in result:
                return result  # 已经是 MCP 格式
            return {
                "content": [{"type": "text", "text": str(result)}],
                "isError": False,
            }
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return {
                "content": [{"type": "text", "text": f"执行错误: {str(e)}"}],
                "isError": True,
            }

    async def _execute_on_main_thread(self, handler: Callable, arguments: dict) -> Any:
        """在 DCC 主线程执行工具 handler（通过 Future 等待结果）"""
        import concurrent.futures
        future = concurrent.futures.Future()

        def _run():
            try:
                result = handler(arguments)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)

        self._main_thread_executor(_run)

        # 在 asyncio 中等待 concurrent.futures.Future
        loop = asyncio.get_event_loop()
        return await asyncio.wrap_future(future, loop=loop)

    # --- Tool 注册接口 ---

    def register_tool(self, name: str, description: str,
                      input_schema: dict, handler: Callable,
                      main_thread: bool = False) -> None:
        """
        注册 MCP 工具。

        Args:
            name: 工具名称
            description: 工具描述（AI 会看到）
            input_schema: JSON Schema 参数定义
            handler: 执行函数
            main_thread: 是否必须在 DCC 主线程执行
        """
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "_handler": handler,
            "_main_thread": main_thread,
        }
        logger.info(f"Tool registered: {name}" + (" [main_thread]" if main_thread else ""))

    def unregister_tool(self, name: str) -> None:
        if name in self._tools:
            del self._tools[name]

    # --- 服务器生命周期 ---

    def start(self) -> bool:
        """启动 MCP Server（在独立线程中运行 asyncio）"""
        if not _HAS_WEBSOCKETS:
            logger.error("websockets not available. Install: pip install websockets")
            return False

        if self._running:
            logger.warning("MCP Server already running")
            return True

        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="ArtClaw-MCP"
        )
        self._thread.start()

        # 等待启动
        deadline = time.time() + 5.0
        while time.time() < deadline and not self._running:
            time.sleep(0.1)

        return self._running

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_server())
            if self._running:
                self._loop.run_forever()
        except Exception as e:
            logger.error(f"MCP Server loop error: {e}")
        finally:
            self._loop.close()
            self._loop = None

    async def _start_server(self) -> None:
        self._actual_port = self._find_available_port()

        for attempt in range(MAX_PORT_PROBE):
            try:
                self._server = await ws_serve(
                    self._connection_handler,
                    self._host,
                    self._actual_port,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=WS_PING_TIMEOUT,
                )
                break
            except OSError as e:
                if "address already in use" in str(e).lower() or getattr(e, "errno", 0) == 10048:
                    logger.warning(f"Port {self._actual_port} occupied, trying next...")
                    self._actual_port += 1
                else:
                    raise
        else:
            logger.error(f"Failed to bind any port in range {self._port}-{self._actual_port}")
            return

        self._running = True
        logger.info(f"MCP Server started: {self.server_address}")

    def stop(self) -> None:
        """停止 MCP Server"""
        if not self._running:
            return

        self._running = False

        if self._loop and self._loop.is_running():
            # 在事件循环中安排关闭
            async def _shutdown():
                if self._clients:
                    for ws in list(self._clients):
                        try:
                            await ws.close(1001, "Server shutting down")
                        except Exception:
                            pass
                    self._clients.clear()
                    self._initialized_clients.clear()

                if self._server:
                    self._server.close()
                    await self._server.wait_closed()
                    self._server = None

                self._loop.stop()

            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._actual_port = None
        self._thread = None
        logger.info("MCP Server stopped")


# --- 全局实例 ---

_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> Optional[MCPServer]:
    return _mcp_server


def start_mcp_server(adapter=None, port: int = DEFAULT_PORT) -> bool:
    """
    启动 MCP Server。

    Args:
        adapter: DCC adapter 实例（提供主线程执行器）
        port: 起始端口
    """
    global _mcp_server

    if _mcp_server is not None and _mcp_server.is_running:
        return True

    _mcp_server = MCPServer(port=port)

    # 注入主线程执行器
    if adapter:
        _mcp_server._main_thread_executor = adapter.execute_deferred

    # 注册内置工具
    _register_builtin_tools(_mcp_server, adapter)

    return _mcp_server.start()


def _register_builtin_tools(server: MCPServer, adapter=None) -> None:
    """注册内置 MCP 工具"""

    # --- run_python: 万能执行器 ---
    def _handle_run_python(arguments: dict) -> dict:
        code = arguments.get("code", "")
        if not code:
            return {"content": [{"type": "text", "text": "错误: 未提供代码"}], "isError": True}

        if adapter:
            result = adapter.execute_code(code)
            output_parts = []
            if result.get("output"):
                output_parts.append(result["output"])
            if result.get("error"):
                output_parts.append(f"错误: {result['error']}")
            elif result.get("result") is not None:
                output_parts.append(f"返回值: {result['result']}")

            text = "\n".join(output_parts) if output_parts else "执行完成 (无输出)"
            return {
                "content": [{"type": "text", "text": text}],
                "isError": not result.get("success", False),
            }
        else:
            return {"content": [{"type": "text", "text": "错误: DCC adapter 未初始化"}], "isError": True}

    server.register_tool(
        name="run_python",
        description="在 DCC 软件中执行 Python 代码。上下文变量: S=选中对象列表, W=当前场景文件, L=DCC命令模块。所有写操作都有 Undo 支持。",
        input_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                },
            },
            "required": ["code"],
        },
        handler=_handle_run_python,
        main_thread=True,
    )

    # --- get_editor_context: 编辑器上下文 ---
    def _handle_get_editor_context(arguments: dict) -> str:
        if not adapter:
            return "DCC adapter 未初始化"
        try:
            info = {
                "software": adapter.get_software_name(),
                "version": adapter.get_software_version(),
                "python": adapter.get_python_version(),
                "current_file": adapter.get_current_file() or "untitled",
            }
            return json.dumps(info, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"错误: {e}"

    server.register_tool(
        name="get_editor_context",
        description="获取当前 DCC 软件的基本信息（软件名、版本、当前文件等）",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_editor_context,
        main_thread=True,
    )

    # --- get_selected_objects: 选中对象 ---
    def _handle_get_selected_objects(arguments: dict) -> str:
        if not adapter:
            return "DCC adapter 未初始化"
        try:
            objects = adapter.get_selected_objects()
            if not objects:
                return "当前没有选中对象"
            return json.dumps(objects, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"错误: {e}"

    server.register_tool(
        name="get_selected_objects",
        description="获取当前选中的对象列表（名称、类型、路径）",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_selected_objects,
        main_thread=True,
    )

    # --- get_scene_info: 场景信息 ---
    def _handle_get_scene_info(arguments: dict) -> str:
        if not adapter:
            return "DCC adapter 未初始化"
        try:
            info = adapter.get_scene_info()
            return json.dumps(info, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"错误: {e}"

    server.register_tool(
        name="get_scene_info",
        description="获取当前场景概览信息（对象数、Mesh数、帧范围、FPS、场景文件路径等）",
        input_schema={"type": "object", "properties": {}},
        handler=_handle_get_scene_info,
        main_thread=True,
    )

    logger.info(f"Registered {len(server._tools)} builtin tools")


def stop_mcp_server() -> None:
    """停止 MCP Server"""
    global _mcp_server
    if _mcp_server:
        _mcp_server.stop()
        _mcp_server = None
