"""
mcp_server.py - MCP WebSocket 通信网关
========================================

阶段 1.1: MCP WebSocket 通信网关

宪法约束:
  - 开发路线图 §1.1: 基于 websockets 库的服务器，自动端口探测(8080+)，断线自动重置
  - 系统架构设计 §1.2: WebSocket 传输，JSON-RPC 2.0 封装，MCP 1.0 规范
  - 系统架构设计 §1.3: 驻留 UE 进程，支持多客户端并发连接
  - 概要设计 §核心设计: C++ 负责生命周期/主线程调度，Python 负责 MCP 通信

设计说明:
  - asyncio 事件循环通过 unreal.register_slate_post_tick_callback 驱动
  - 不创建额外线程，所有异步任务在 UE 主线程的 tick 间隙执行
  - 避免线程安全问题：所有 unreal API 调用都在主线程上
"""

import asyncio
import json
import os
import socket
from typing import Optional, Dict, Set, Any

try:
    import websockets
    from websockets.server import serve as ws_serve
    from websockets.exceptions import ConnectionClosed
    _HAS_WEBSOCKETS = True
except ImportError:
    _HAS_WEBSOCKETS = False

import unreal

# 从 claw_bridge_logger 导入日志系统
from claw_bridge_logger import UELogger, log_mcp_call


# ============================================================================
# 1. MCP 协议常量
# ============================================================================

MCP_VERSION = "2024-11-05"
JSONRPC_VERSION = "2.0"

# 默认端口范围
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
MAX_PORT_PROBE = 100  # 最多尝试 100 个端口

# WebSocket 心跳配置
WS_PING_INTERVAL = 20  # 秒
WS_PING_TIMEOUT = 10   # 秒

# 服务器信息
SERVER_NAME = "UE Claw Bridge"
SERVER_VERSION = "1.0.0"


# ============================================================================
# 2. JSON-RPC 辅助
# ============================================================================

def _make_jsonrpc_response(request_id: Any, result: Any) -> str:
    """构造 JSON-RPC 2.0 成功响应"""
    return json.dumps({
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "result": result,
    })


def _make_jsonrpc_error(request_id: Any, code: int, message: str, data: Any = None) -> str:
    """构造 JSON-RPC 2.0 错误响应"""
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return json.dumps({
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": error,
    })


def _make_jsonrpc_notification(method: str, params: Any = None) -> str:
    """构造 JSON-RPC 2.0 通知（无 id）"""
    msg = {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
    }
    if params is not None:
        msg["params"] = params
    return json.dumps(msg)


# JSON-RPC 标准错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# ============================================================================
# 3. Tool 事件写入 stream.jsonl — 委托给通用 tool_event_writer
# ============================================================================

try:
    from tool_event_writer import write_tool_event as _write_tool_event, set_stream_file_provider
except ImportError:
    # fallback: 通用模块未部署时静默降级
    def _write_tool_event(*a, **kw): pass
    def set_stream_file_provider(fn): pass


def _get_active_stream_file() -> str:
    """获取当前活跃的 stream.jsonl 路径。仅在 chat 请求进行中时存在。"""
    try:
        import unreal
        # 必须用 UE 的绝对路径转换！与 C++ FPaths::ConvertRelativePathToFull 一致。
        # os.path.abspath 基于 CWD，和 UE 项目根不同。
        saved_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    except Exception:
        return ""
    stream_file = os.path.join(saved_dir, "ClawBridge", "_openclaw_response_stream.jsonl")
    response_file = os.path.join(saved_dir, "ClawBridge", "_openclaw_response.txt")
    if os.path.exists(response_file):
        return ""  # chat 已完成，不写
    return stream_file

# 注册 UE 专用的 stream file provider
set_stream_file_provider(_get_active_stream_file)


def _write_tool_event_to_stream(event_type: str, tool_name: str, *,
                                 arguments=None, result=None, is_error=False):
    """兼容层：调用通用 tool_event_writer。"""
    _write_tool_event(event_type, tool_name, arguments=arguments, result=result)


# ============================================================================
# 4. MCPServer 核心类
# ============================================================================

class MCPServer:
    """
    MCP WebSocket 通信网关。

    宪法约束:
      - 系统架构设计 §1.3: 驻留 UE 进程内，统一分发指令
      - 概要设计 §1.1: 统一管理中心，多方接入
      - 核心机制 §1: 自动能力发现

    设计:
      - 基于 asyncio + websockets 实现异步服务器
      - 通过 slate_post_tick 驱动事件循环（不阻塞 UE 主线程）
      - 支持多客户端并发连接
      - 自动端口探测 + 断线自动重置
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._host = host
        self._port = port
        self._actual_port: Optional[int] = None

        # asyncio 事件循环
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None

        # 连接管理
        self._clients: Set = set()
        self._client_info: Dict[int, dict] = {}  # websocket id -> info

        # 状态
        self._running = False
        self._tick_handle = None

        # MCP 协议状态
        self._initialized_clients: Set[int] = set()

        # Tool 注册表 (由外部模块注册)
        self._tools: Dict[str, dict] = {}

        # Resource 注册表 (阶段 2.2)
        self._resource_definitions: list = []
        self._resource_reader = None  # callable(uri) -> dict
        self._resource_handlers: Dict[str, Any] = {}  # uri -> handler

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

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # --- 端口探测 ---

    @staticmethod
    def _is_port_available(host: str, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.bind((host, port))
                return True
        except OSError:
            return False

    def _find_available_port(self) -> int:
        """
        自动端口探测：从 self._port 开始，逐个检查到 self._port + MAX_PORT_PROBE。

        宪法约束:
          - 开发路线图 §1.1: 自动端口探测（8080+）
        """
        for offset in range(MAX_PORT_PROBE):
            candidate = self._port + offset
            if self._is_port_available(self._host, candidate):
                if offset > 0:
                    UELogger.info(f"Port {self._port} occupied, using {candidate}")
                return candidate

        # 所有端口都被占用，回退到默认端口让 OS 报错
        UELogger.warning(
            f"All ports {self._port}-{self._port + MAX_PORT_PROBE} occupied, "
            f"falling back to {self._port}"
        )
        return self._port

    # --- WebSocket 连接处理 ---

    async def _connection_handler(self, websocket):
        """
        处理单个 WebSocket 客户端连接。

        宪法约束:
          - 开发路线图 §1.1: 断线自动重置
          - 系统架构设计 §1.3: Multi-Client Coordinator
        """
        client_id = id(websocket)
        remote = websocket.remote_address
        self._clients.add(websocket)
        self._client_info[client_id] = {
            "remote": f"{remote[0]}:{remote[1]}" if remote else "unknown",
            "initialized": False,
        }

        UELogger.mcp(f"Client connected: {self._client_info[client_id]['remote']} "
                      f"(total: {len(self._clients)})")

        try:
            async for raw_message in websocket:
                try:
                    response = await self._handle_message(websocket, raw_message)
                    if response:
                        await websocket.send(response)
                except Exception as e:
                    UELogger.mcp_error(f"Message handling error: {e}")
                    # 尝试发送错误响应
                    try:
                        error_resp = _make_jsonrpc_error(
                            None, INTERNAL_ERROR,
                            f"Internal server error: {str(e)}"
                        )
                        await websocket.send(error_resp)
                    except Exception:
                        pass

        except ConnectionClosed as e:
            UELogger.mcp(f"Client disconnected: {self._client_info.get(client_id, {}).get('remote', '?')} "
                         f"(code={e.code}, reason={e.reason})")
        except Exception as e:
            UELogger.mcp_error(f"Connection error: {e}")
        finally:
            # 清理连接
            self._clients.discard(websocket)
            self._initialized_clients.discard(client_id)
            self._client_info.pop(client_id, None)

            UELogger.mcp(f"Client cleaned up (remaining: {len(self._clients)})")

    # --- MCP 消息处理 ---

    @log_mcp_call
    async def _handle_message(self, websocket, raw_message: str) -> Optional[str]:
        """
        处理收到的 JSON-RPC 消息，路由到对应的 MCP 方法。

        宪法约束:
          - 系统架构设计 §1.2: JSON-RPC 2.0 封装，MCP 1.0 规范
        """
        # 解析 JSON
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError as e:
            return _make_jsonrpc_error(None, PARSE_ERROR, f"JSON parse error: {e}")

        # 验证 JSON-RPC 格式
        if not isinstance(msg, dict) or msg.get("jsonrpc") != JSONRPC_VERSION:
            return _make_jsonrpc_error(
                msg.get("id"), INVALID_REQUEST,
                "Invalid JSON-RPC 2.0 request"
            )

        method = msg.get("method", "")
        params = msg.get("params", {})
        request_id = msg.get("id")  # 通知消息没有 id

        # 路由到处理方法
        handler = self._get_method_handler(method)
        if handler is None:
            if request_id is not None:
                return _make_jsonrpc_error(
                    request_id, METHOD_NOT_FOUND,
                    f"Method not found: {method}"
                )
            return None  # 通知消息不需要响应

        try:
            result = await handler(websocket, params)
            if request_id is not None:
                return _make_jsonrpc_response(request_id, result)
            return None  # 通知消息不需要响应
        except Exception as e:
            UELogger.mcp_error(f"Handler error for {method}: {e}")
            if request_id is not None:
                return _make_jsonrpc_error(
                    request_id, INTERNAL_ERROR,
                    f"Handler error: {str(e)}"
                )
            return None

    def _get_method_handler(self, method: str):
        """获取 MCP 方法的处理函数"""
        handlers = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
        }
        return handlers.get(method)

    # --- MCP 协议方法实现 ---

    async def _handle_initialize(self, websocket, params: dict) -> dict:
        """
        MCP initialize 握手。

        返回服务器能力声明。

        宪法约束:
          - 概要设计 §2.2: MCP Tool 封装
          - 核心机制 §1: 自动能力发现
        """
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion", "unknown")

        client_id = id(websocket)
        UELogger.mcp(
            f"Initialize request from {client_info.get('name', 'unknown')} "
            f"(protocol: {protocol_version})"
        )

        return {
            "protocolVersion": MCP_VERSION,
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": False, "listChanged": True},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        }

    async def _handle_initialized(self, websocket, params: dict) -> None:
        """MCP initialized 通知 - 客户端确认握手完成"""
        client_id = id(websocket)
        self._initialized_clients.add(client_id)
        info = self._client_info.get(client_id, {})
        info["initialized"] = True
        UELogger.mcp(f"Client initialized: {info.get('remote', '?')}")

    async def _handle_ping(self, websocket, params: dict) -> dict:
        """心跳响应"""
        return {}

    async def _handle_tools_list(self, websocket, params: dict) -> dict:
        """
        返回可用 Tool 列表。

        宪法约束:
          - 概要设计 §2.3: tools/unreal://skills/list
          - 核心机制 §1: 自动能力发现，Schema 转换
        """
        # 剔除内部字段 _handler，只返回协议定义
        tools = []
        for tool in self._tools.values():
            tools.append({k: v for k, v in tool.items() if not k.startswith("_")})
        UELogger.mcp(f"tools/list -> {len(tools)} tools")
        return {"tools": tools}

    async def _handle_tools_call(self, websocket, params: dict) -> dict:
        """
        执行 Tool 调用。

        宪法约束:
          - 概要设计 §2.3: tools/unreal://skills/execute
          - 核心机制 §3: 安全可逆执行
        """
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        UELogger.mcp(f"tools/call -> {tool_name}({arguments})")

        # 写入 tool 调用开始事件到 stream.jsonl（方案 2: MCP 侧记录）
        # 只用 tool_use_text 轻量文本，融入消息流，不占空间
        _write_tool_event_to_stream("start", tool_name, arguments=arguments)

        # 查找并执行 handler
        tool_def = self._tools[tool_name]
        handler = tool_def.get("_handler")
        if handler is None:
            raise ValueError(f"Tool '{tool_name}' has no handler")

        try:
            result = await handler(arguments) if asyncio.iscoroutinefunction(handler) else handler(arguments)
            _write_tool_event_to_stream("done", tool_name, result=result)
            return {
                "content": [
                    {"type": "text", "text": str(result)}
                ],
                "isError": False,
            }
        except Exception as e:
            UELogger.mcp_error(f"Tool execution error ({tool_name}): {e}")
            _write_tool_event_to_stream("error", tool_name, result=str(e)[:200])
            return {
                "content": [
                    {"type": "text", "text": f"Error: {str(e)}"}
                ],
                "isError": True,
            }

    async def _handle_resources_list(self, websocket, params: dict) -> dict:
        """
        返回可用 Resource 列表。

        宪法约束:
          - 开发路线图 §2.2: UE 编辑器状态映射为 MCP 资源 URI
          - 核心机制 §6: MCP 资源流转
        """
        UELogger.mcp(f"resources/list -> {len(self._resource_definitions)} resources")
        return {"resources": self._resource_definitions}

    async def _handle_resources_read(self, websocket, params: dict) -> dict:
        """
        读取指定 Resource。

        宪法约束:
          - 开发路线图 §2.2: AI 通过读取资源实时获取当前状态
          - 核心机制 §6: 懒加载 + 按需采样
        """
        uri = params.get("uri", "")
        UELogger.mcp(f"resources/read -> {uri}")

        # 优先使用 per-URI handler
        if uri in self._resource_handlers:
            handler = self._resource_handlers[uri]
            content_text = handler() if callable(handler) else str(handler)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": content_text,
                    }
                ]
            }

        # 回退到全局 resource_reader
        if self._resource_reader is not None:
            content = self._resource_reader(uri)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(content, default=str),
                    }
                ]
            }

        raise ValueError(f"No handler for resource: {uri}")

    # --- Tool 注册接口 ---

    # --- Resource 注册接口 ---

    def register_resource(self, uri: str, name: str, description: str,
                          handler=None, mime_type: str = "application/json") -> None:
        """
        注册一个 MCP Resource。

        Args:
            uri: 资源 URI (e.g. "unreal://engine/version")
            name: 人类可读名称
            description: 描述
            handler: 读取函数，返回字符串内容
            mime_type: MIME 类型

        宪法约束:
          - 开发路线图 §2.2: UE 编辑器状态映射为 MCP 资源 URI
        """
        self._resource_definitions.append({
            "uri": uri,
            "name": name,
            "description": description,
            "mimeType": mime_type,
        })
        if handler is not None:
            self._resource_handlers[uri] = handler
        UELogger.info(f"Resource registered: {uri}")

    # --- Tool 注册接口 ---

    def register_tool(self, name: str, description: str,
                      input_schema: dict, handler) -> None:
        """
        注册一个 MCP Tool。

        Args:
            name: Tool 名称（唯一标识）
            description: Tool 描述（AI 会看到）
            input_schema: JSON Schema（参数定义）
            handler: 执行函数 (sync or async)

        宪法约束:
          - 核心机制 §1: 自动能力发现，Schema 转换
        """
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "_handler": handler,  # 内部字段，不会序列化给客户端
        }
        UELogger.info(f"Tool registered: {name}")

    def unregister_tool(self, name: str) -> None:
        """注销一个 MCP Tool"""
        if name in self._tools:
            del self._tools[name]
            UELogger.info(f"Tool unregistered: {name}")

    # --- 通知广播 ---

    async def broadcast_notification(self, method: str, params: Any = None) -> None:
        """
        向所有已初始化的客户端广播通知。

        宪法约束:
          - 系统架构设计 §1.3: Multi-Client Coordinator，关键事件推送
          - 概要设计 §2.1: 关键推送 (Critical Push)
        """
        if not self._clients:
            return

        message = _make_jsonrpc_notification(method, params)
        # 只向已完成 initialize 握手的客户端发送
        targets = [
            ws for ws in self._clients
            if id(ws) in self._initialized_clients
        ]

        if not targets:
            return

        UELogger.mcp(f"Broadcasting {method} to {len(targets)} clients")
        results = await asyncio.gather(
            *[ws.send(message) for ws in targets],
            return_exceptions=True,
        )
        for ws, result in zip(targets, results):
            if isinstance(result, Exception):
                UELogger.mcp_error(f"Broadcast failed to {id(ws)}: {result}")

    # --- 服务器生命周期 ---

    async def _start_server(self) -> None:
        """启动 WebSocket 服务器（内部异步方法）"""
        self._actual_port = self._find_available_port()

        # 尝试绑定，如果端口仍被占用（竞态条件/热重载残留），自动递增
        max_retries = MAX_PORT_PROBE
        for attempt in range(max_retries):
            try:
                self._server = await ws_serve(
                    self._connection_handler,
                    self._host,
                    self._actual_port,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=WS_PING_TIMEOUT,
                )
                break  # 绑定成功
            except OSError as e:
                if e.errno == 10048 or "address already in use" in str(e).lower():
                    UELogger.warning(
                        f"Port {self._actual_port} still occupied "
                        f"(attempt {attempt+1}/{max_retries}), trying next..."
                    )
                    self._actual_port += 1
                else:
                    raise
        else:
            UELogger.mcp_error(
                f"Failed to bind any port in range "
                f"{self._port}-{self._actual_port}"
            )
            return

        self._running = True
        UELogger.info(f"MCP Server started: {self.server_address}")

        # 同步端口信息到 C++ Subsystem
        try:
            subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
            if subsystem and hasattr(subsystem, 'set_server_port'):
                subsystem.set_server_port(self._actual_port)
        except Exception:
            pass  # 方法可能尚未在 C++ 侧定义

        # 同步 MCP 就绪状态到 bridge 状态文件
        try:
            import openclaw_ws, os
            _status_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "..", "Saved", "ClawBridge")
            openclaw_ws.write_bridge_status(_status_dir, connected=True, mcp_ready=True)
        except Exception:
            pass

    async def _stop_server(self) -> None:
        """停止 WebSocket 服务器（内部异步方法）"""
        self._running = False

        # 关闭所有客户端连接
        if self._clients:
            UELogger.mcp(f"Closing {len(self._clients)} client connections...")
            close_tasks = []
            for ws in list(self._clients):
                close_tasks.append(ws.close(1001, "Server shutting down"))
            await asyncio.gather(*close_tasks, return_exceptions=True)
            self._clients.clear()
            self._client_info.clear()
            self._initialized_clients.clear()

        # 关闭服务器
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        self._actual_port = None

        # 同步 MCP 停止状态到 bridge 状态文件
        try:
            import openclaw_ws, os
            _status_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "..", "Saved", "ClawBridge")
            openclaw_ws.write_bridge_status(_status_dir, connected=True, mcp_ready=False)
        except Exception:
            pass

        UELogger.info("MCP Server stopped")


# ============================================================================
# 5a. asyncio 事件循环与 UE Tick 集成
# ============================================================================

class _UEAsyncBridge:
    """
    将 asyncio 事件循环集成到 UE 编辑器的 Slate Tick 中。

    核心机制:
      - 创建一个独立的 asyncio 事件循环（不是 running 状态的）
      - 每次 UE Slate tick 时，手动推进事件循环一小步
      - 这样 asyncio 协程可以在不阻塞 UE 的情况下运行

    宪法约束:
      - 开发路线图 §1.5: 主线程调度器 (GameThread Marshalling)
      - 概要设计: C++ 负责主线程调度
    """

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tick_handle = None
        self._server: Optional[MCPServer] = None

    def start(self, server: MCPServer) -> bool:
        """启动异步桥接"""
        if self._loop is not None:
            UELogger.warning("Async bridge already running")
            return False

        self._server = server

        # 创建新的事件循环（不 set 为当前线程的）
        self._loop = asyncio.new_event_loop()

        # 在事件循环中调度服务器启动
        self._loop.create_task(server._start_server())
        server._loop = self._loop

        # 注册 Slate tick 回调
        self._tick_handle = unreal.register_slate_post_tick_callback(self._on_tick)

        UELogger.info("Async bridge started (SlatePostTick)")
        return True

    def stop(self) -> None:
        """停止异步桥接"""
        if self._loop is None:
            return

        # 注销 tick 回调
        if self._tick_handle is not None:
            unreal.unregister_slate_post_tick_callback(self._tick_handle)
            self._tick_handle = None

        # 停止服务器
        if self._server and self._server.is_running:
            # 在事件循环中调度停止
            self._loop.run_until_complete(self._server._stop_server())

        # 清理事件循环
        try:
            # 取消所有挂起的任务
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.close()
        except Exception as e:
            UELogger.warning(f"Event loop cleanup warning: {e}")

        self._loop = None
        self._server = None
        UELogger.info("Async bridge stopped")

    def _on_tick(self, delta_time: float) -> None:
        """
        每次 Slate tick 时推进 asyncio 事件循环。

        这是核心机制：让 asyncio 协程在 UE 主线程上增量执行，
        不阻塞编辑器 UI。

        每次 tick 多跑几轮 step，加速启动阶段的 asyncio 任务完成。
        """
        if self._loop is None or self._loop.is_closed():
            return

        try:
            # 多跑几轮，加速 websockets server 启动
            # 每轮只执行就绪回调，不会阻塞
            for _ in range(10):
                self._loop.stop()
                self._loop.run_forever()
        except Exception as e:
            UELogger.error(f"Async tick error: {e}")


# ============================================================================
# 5. 全局实例与公共接口
# ============================================================================

# 全局单例
_mcp_server: Optional[MCPServer] = None
_async_bridge: Optional[_UEAsyncBridge] = None


def get_mcp_server() -> Optional[MCPServer]:
    """获取 MCP 服务器单例（供其他模块注册 Tool 等）"""
    return _mcp_server


def start_mcp_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """
    启动 MCP WebSocket 通信网关。

    在 init_unreal.py 初始化完成后调用。

    Args:
        host: 监听地址（默认 localhost）
        port: 起始端口（默认 8080，自动探测可用端口）

    Returns:
        True 如果启动成功

    宪法约束:
      - 开发路线图 §1.1: WebSocket 服务器在插件启动时自动启动
    """
    global _mcp_server, _async_bridge

    if not _HAS_WEBSOCKETS:
        UELogger.error(
            "websockets library not available! "
            "MCP Server cannot start. "
            "Please install: pip install websockets>=12.0"
        )
        return False

    if _mcp_server is not None and _mcp_server.is_running:
        UELogger.warning("MCP Server is already running")
        return True

    try:
        _mcp_server = MCPServer(host=host, port=port)
        _async_bridge = _UEAsyncBridge()

        success = _async_bridge.start(_mcp_server)
        if success:
            UELogger.info(f"MCP Gateway initializing on {host}:{port}+")

            # --- 阶段 1.2~1.6: 注册核心工具 ---
            _register_builtin_tools(_mcp_server)

            # --- 阶段 3: 智能与优化子系统 ---
            _init_phase3_subsystems(_mcp_server)

            # --- Tool Manager 事件桥接 ---
            try:
                from tool_event_bridge import init_tool_event_bridge
                bridge = init_tool_event_bridge()
                if bridge:
                    UELogger.info("Tool Event Bridge: active (forwarding DCC events to Tool Manager)")
                else:
                    UELogger.info("Tool Event Bridge: skipped (Tool Manager not running or Subsystem unavailable)")
            except Exception as e:
                UELogger.warning(f"Tool Event Bridge init failed: {e}")

        return success

    except Exception as e:
        UELogger.exception(f"Failed to start MCP Server")
        _mcp_server = None
        _async_bridge = None
        return False


def _register_builtin_tools(server: MCPServer) -> None:
    """
    注册所有内置 MCP 工具和资源。

    宪法约束:
      - 核心机制 §1: 自动能力发现
      - 开发路线图 §1.2: run_ue_python 注册
      - 开发路线图 §2.2: MCP Resources 注册
    """
    # 阶段 1: 万能执行器
    try:
        from tools.universal_proxy import register_tools as register_phase1
        register_phase1(server)
    except Exception:
        UELogger.exception("Failed to register Phase 1 tools")

    # 阶段 2.2/2.4/2.5/2.6: 上下文感知 + 视口操作 + 资源映射
    try:
        from tools.context_provider import register_tools as register_phase2_ctx
        from tools.context_provider import register_resources as register_phase2_res
        register_phase2_ctx(server)
        register_phase2_res(server)
    except Exception:
        UELogger.exception("Failed to register Phase 2 context tools")

    # 阶段 2.3: 风险分级确认
    try:
        from tools.risk_confirmation import register_tools as register_phase2_risk
        register_phase2_risk(server)
    except Exception:
        UELogger.exception("Failed to register Phase 2.3 risk tools")

    # 阶段 2.7: 自修复
    try:
        from tools.self_healing import register_tools as register_phase2_heal
        register_phase2_heal(server)
    except Exception:
        UELogger.exception("Failed to register Phase 2.7 self-healing tools")


def _init_phase3_subsystems(server: MCPServer) -> None:
    """
    初始化阶段 3 的所有子系统。

    宪法约束:
      - 开发路线图 §3: 智能与优化
      - 系统架构设计 §1.5: Core Tool / Skill 二层体系
    """
    # §3.5 版本适配器 — 最先初始化，其他模块可能依赖它
    try:
        from ue_version_adapter import init_version_adapter
        adapter = init_version_adapter(server)
        UELogger.info(f"Phase 3.5: Version Adapter ready ({adapter.version})")
    except Exception:
        UELogger.exception("Phase 3.5: Failed to init version adapter")

    # §3.4 记忆存储
    try:
        from memory_store import init_memory_store
        memory = init_memory_store(server)
        UELogger.info(f"Phase 3.4: Memory Store ready")
    except Exception:
        UELogger.exception("Phase 3.4: Failed to init memory store")

    # §3.2 + 3.3 + 3.6 知识库
    try:
        from knowledge_base import init_knowledge_base
        kb = init_knowledge_base(server)
        UELogger.info(f"Phase 3.2: Knowledge Base ready ({kb.get_stats()['total_documents']} docs)")
    except Exception:
        UELogger.exception("Phase 3.2: Failed to init knowledge base")

    # §3.1 Skill Hub — 最后初始化，依赖 MCP Server 已就绪
    # Phase B: 增强版 — 分层加载、manifest 解析、版本匹配、冲突检测
    try:
        from skill_hub import init_skill_hub
        hub = init_skill_hub(server)

        UELogger.info(f"Phase 3.1: Skill Hub ready ({len(hub._registered_skills)} skills)")

        # Phase B5: 注册 Skill 管理 MCP Tools
        try:
            from skill_mcp_tools import register_skill_tools
            register_skill_tools(server, hub)
            UELogger.info("Phase B5: Skill management MCP tools registered")
        except Exception:
            UELogger.exception("Phase B5: Failed to register skill management tools")

        # Phase B6: 注册 Skill 管理 MCP Resources
        try:
            from skill_mcp_resources import register_skill_resources
            register_skill_resources(server, hub)
            UELogger.info("Phase B6: Skill management MCP resources registered")
        except Exception:
            UELogger.exception("Phase B6: Failed to register skill management resources")

    except Exception:
        UELogger.exception("Phase 3.1: Failed to init skill hub")


def stop_mcp_server() -> None:
    """
    停止 MCP WebSocket 通信网关。

    在编辑器关闭时调用。
    """
    global _mcp_server, _async_bridge

    # 先关闭 Tool Event Bridge
    try:
        from tool_event_bridge import shutdown_tool_event_bridge
        shutdown_tool_event_bridge()
    except Exception:
        pass

    if _async_bridge is not None:
        try:
            _async_bridge.stop()
        except Exception as e:
            UELogger.warning(f"Error stopping async bridge: {e}")

    _async_bridge = None
    _mcp_server = None
    UELogger.info("MCP Gateway shutdown complete")
