"""
bootstrap.py - UnityClawBridge Python 端入口
=============================================

职责：
1. 启动 MCP Server（WebSocket，端口 8088）
2. 注册 run_unity_python 工具
3. 通过 HTTP API 与 Unity Editor 进程交互

架构：
  Python MCP Server --HTTP POST /execute--> Unity C# CommandServer
  CommandServer --EditorApplication.update--> Roslyn 执行
  Python MCP Server --HTTP GET /result/{id}--> CommandServer

运行：
  python bootstrap.py --port 8088
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# sys.path：按优先级查找 core/ 和 mcp_server.py
_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent  # UnityClawBridge/
_UNITY_ASSETS = _SCRIPT_DIR.parent.parent  # Assets/ (Unity 安装模式)

def _get_config_project_root() -> Optional[Path]:
    """从 ~/.artclaw/config.json 读取 project_root"""
    try:
        cfg_path = Path.home() / ".artclaw" / "config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            root = cfg.get("project_root")
            if root and Path(root).is_dir():
                return Path(root)
    except Exception as e:
        print(f"[ArtClaw] 读取 config.json 失败: {e}", file=sys.stderr)
    return None

_artclaw_root = _get_config_project_root()
for _p in [
    (_artclaw_root / "core") if _artclaw_root else None,
    _UNITY_ASSETS / "core",
    _PLUGIN_ROOT.parent.parent / "core",
]:
    if _p and _p.exists():
        _p_str = str(_p.resolve())
        if _p_str not in sys.path:
            sys.path.insert(0, _p_str)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="[ArtClaw|Unity] %(levelname)s %(message)s",
)
logger = logging.getLogger("artclaw.unity")


# ════════════════════════════════════════════════════════════════════════════════
# 内联 MCPServer（MCP 协议 WebSocket 服务端）
# ════════════════════════════════════════════════════════════════════════════════

class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Any
    main_thread: bool = False


class ToolCall:
    name: str
    arguments: Dict[str, Any]
    call_id: str


class ToolResult:
    def __init__(self, call_id: str, success: bool, content: List[Dict], is_error: bool = False,
                 error_message: Optional[str] = None, duration_ms: float = 0):
        self.call_id = call_id
        self.success = success
        self.content = content
        self.is_error = is_error
        self.error_message = error_message
        self.duration_ms = duration_ms


class MCPServer:
    """ArtClaw MCP Server（WebSocket 模式）"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8088):
        self.host = host
        self.port = port
        self._tools: Dict[str, ToolDefinition] = {}
        self._running = False
        self._start_time = time.time()

    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any],
                      handler: Any, main_thread: bool = False) -> None:
        self._tools[name] = ToolDefinition()
        self._tools[name].name = name
        self._tools[name].description = description
        self._tools[name].input_schema = input_schema
        self._tools[name].handler = handler
        self._tools[name].main_thread = main_thread
        logger.info(f"注册工具: {name}")

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in self._tools.values()
        ]

    async def handle_tool_call(self, call: ToolCall) -> ToolResult:
        start = time.time()
        tool = self._tools.get(call.name)
        if not tool:
            return ToolResult(call_id=call.call_id, success=False, content=[],
                              is_error=True, error_message=f"未知工具: {call.name}",
                              duration_ms=(time.time() - start) * 1000)
        try:
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(call.arguments)
            else:
                result = tool.handler(call.arguments)
            if isinstance(result, dict):
                content = result.get("content", [])
                is_error = result.get("isError", False)
                error_msg = result.get("error")
            else:
                content = [{"type": "text", "text": str(result)}]
                is_error = False
                error_msg = None
            return ToolResult(call_id=call.call_id, success=not is_error, content=content,
                              is_error=is_error, error_message=error_msg,
                              duration_ms=(time.time() - start) * 1000)
        except Exception as e:
            logger.error(f"工具 {call.name} 执行异常: {e}")
            return ToolResult(call_id=call.call_id, success=False, content=[],
                              is_error=True, error_message=str(e),
                              duration_ms=(time.time() - start) * 1000)

    async def _run(self) -> None:
        self._running = True
        logger.info(f"MCP Server 启动 ws://{self.host}:{self.port}")
        try:
            import websockets
        except ImportError:
            logger.error("缺少依赖: pip install websockets")
            return
        async with websockets.serve(self._handle_client, self.host, self.port,
                                     reuse_address=True):
            await asyncio.Future()

    async def _handle_client(self, websocket) -> None:
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
                    await websocket.send(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}))
                except Exception as e:
                    logger.error(f"处理消息异常: {e}")
                    await websocket.send(json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}))
        except Exception as e:
            logger.warning(f"客户端 {client_id} 断开: {e}")

    async def _process_message(self, req: Dict) -> Optional[Dict]:
        method = req.get("method", "")
        req_id = req.get("id")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "artclaw-mcp-server", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            }}
        if method == "notifications/initialized":
            return None
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.get_tools()}}
        if method == "tools/call":
            params = req.get("params", {})
            result = await self.handle_tool_call(ToolCall(
                name=params.get("name", ""), arguments=params.get("arguments", {}),
                call_id=str(uuid.uuid4()),
            ))
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": result.content, "isError": result.is_error}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"status": "ok", "uptime": time.time() - self._start_time}}
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


# ════════════════════════════════════════════════════════════════════════════════
# Unity HTTP 命令通道客户端
# ════════════════════════════════════════════════════════════════════════════════

class UnityCommandChannel:
    def __init__(self, unity_http_port: int = 8089):
        self.base_url = f"http://127.0.0.1:{unity_http_port}"
        self._timeout = 60.0

    async def execute_code(self, code: str) -> dict:
        import aiohttp
        exec_id = str(uuid.uuid4())
        payload = {"id": exec_id, "code": code}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/execute", json=payload,
                                    timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    return {"success": False, "error": f"命令提交失败: HTTP {resp.status} - {body}"}
            deadline = time.time() + self._timeout
            while time.time() < deadline:
                await asyncio.sleep(0.05)
                async with session.get(f"{self.base_url}/result/{exec_id}") as r:
                    data = await r.json()
                    if data.get("done"):
                        return {
                            "success": data.get("success", False),
                            "result": data.get("result"),
                            "error": data.get("error"),
                            "output": data.get("output"),
                        }
            return {"success": False, "error": "执行超时（60秒）"}

    async def health(self) -> dict:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health",
                                       timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    return await resp.json() if resp.status == 200 else {}
        except Exception:
            return {}

    async def logs(self) -> list:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/logs",
                                       timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("logs", [])
        except Exception:
            pass
        return []


# ════════════════════════════════════════════════════════════════════════════════
# 工具处理函数
# ════════════════════════════════════════════════════════════════════════════════

def run_unity_python_handler(args: dict) -> dict:
    """通过 HTTP 向 Unity C# 端提交 C# 代码并获取执行结果"""
    code = args.get("code", "")
    if not code:
        return {"content": [{"type": "text", "text": "错误: code 参数为空"}], "isError": True}
    try:
        import aiohttp
        import asyncio
        channel = UnityCommandChannel()
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(channel.execute_code(code))
        if result.get("success"):
            text = result.get("result") or result.get("output") or "执行成功（无返回值）"
            return {"content": [{"type": "text", "text": f"[OK]\n{text}"}]}
        else:
            return {"content": [{"type": "text", "text": f"[ERROR]\n{result.get('error', '未知错误')}"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"连接 Unity 失败: {e}"}], "isError": True}


def validate_script_handler(args: dict) -> dict:
    import aiohttp
    import asyncio
    code = args.get("code", "")
    try:
        loop = asyncio.get_event_loop()
        resp = loop.run_until_complete(
            aiohttp.ClientSession().post(
                "http://127.0.0.1:8089/validate",
                json={"code": code},
                timeout=aiohttp.ClientTimeout(total=5)
            )
        )
        data = loop.run_until_complete(resp.json())
        if data.get("valid"):
            return {"content": [{"type": "text", "text": "语法正确 ✓"}]}
        else:
            errs = "\n".join(f"  第{e['line']}行: {e['message']}" for e in data.get("errors", []))
            return {"content": [{"type": "text", "text": f"语法错误:\n{errs}"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"连接失败: {e}"}], "isError": True}


def unity_health_handler(args: dict) -> dict:
    import aiohttp
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        data = loop.run_until_complete(
            aiohttp.ClientSession().get(
                "http://127.0.0.1:8089/health",
                timeout=aiohttp.ClientTimeout(total=3)
            )
        )
        health = loop.run_until_complete(data.json())
        text = (f"状态: {health.get('status', '?')}\n"
                f"Unity: {health.get('unity_version', '?')}\n"
                f"项目: {health.get('project_name', '?')}\n"
                f"播放中: {health.get('is_playing', False)}\n"
                f"执行次数: {health.get('execution_count', 0)}")
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"连接失败: {e}"}], "isError": True}


def unity_logs_handler(args: dict) -> dict:
    import aiohttp
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        resp = loop.run_until_complete(
            aiohttp.ClientSession().get(
                "http://127.0.0.1:8089/logs",
                timeout=aiohttp.ClientTimeout(total=3)
            )
        )
        data = loop.run_until_complete(resp.json())
        logs = data.get("logs", [])
        if not logs:
            return {"content": [{"type": "text", "text": "暂无执行日志"}]}
        lines = []
        for e in logs[-20:]:
            icon = "✓" if e.get("success") else "✗"
            ts = e.get("timestamp", "")
            code = e.get("code_preview", "")
            error = e.get("error", "")
            result = e.get("result", "")
            if error:
                lines.append(f"[{ts}] {icon} {code}\n  错误: {error}")
            elif result:
                lines.append(f"[{ts}] {icon} {code}\n  结果: {result}")
            else:
                lines.append(f"[{ts}] {icon} {code}")
        return {"content": [{"type": "text", "text": "最近执行日志：\n" + "\n".join(lines)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"连接失败: {e}"}], "isError": True}


# ════════════════════════════════════════════════════════════════════════════════
# MCP Server 启动
# ════════════════════════════════════════════════════════════════════════════════

async def main(port: int):
    """主入口：启动 MCP WebSocket Server"""
    logger.info(f"UnityClawBridge MCP Server 启动中... 端口={port}")

    server = MCPServer(host="127.0.0.1", port=port)

    server.register_tool(
        name="run_unity_python",
        description="Execute C# code in the Unity Editor main thread using Roslyn. Returns structured JSON result with success/error fields.",
        input_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "C# code to execute. Access Unity APIs directly (UnityEngine, UnityEditor namespaces are imported). Examples: GameObject.Find('Main Camera'), Debug.Log('Hello'), Selection.activeGameObject.name",
                }
            },
            "required": ["code"],
        },
        handler=run_unity_python_handler,
    )

    server.register_tool(
        name="validate_script",
        description="Validate C# code syntax without executing. Use before running complex scripts to catch errors early.",
        input_schema={
            "type": "object",
            "properties": {"code": {"type": "string", "description": "C# code to validate"}},
            "required": ["code"],
        },
        handler=validate_script_handler,
    )

    server.register_tool(
        name="unity_health",
        description="Get Unity Editor health status including version, project name, play mode, and compilation state.",
        input_schema={"type": "object", "properties": {}},
        handler=unity_health_handler,
    )

    server.register_tool(
        name="unity_logs",
        description="Get recent execution logs from Unity CommandServer. Shows last 20 executions with success/failure status.",
        input_schema={"type": "object", "properties": {}},
        handler=unity_logs_handler,
    )

    logger.info(f"已注册 {len(server.get_tools())} 个 MCP 工具")
    await server._run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UnityClawBridge MCP Server")
    parser.add_argument("--port", type=int, default=8088, help="MCP Server WebSocket 端口")
    parser.add_argument("--plugin-root", type=str, default=None, help="(ignored, resolved via config.json)")
    parser.add_argument("--stdio", action="store_true", help="stdio 模式（供 mcporter 等工具使用）")
    args = parser.parse_args()
    if args.stdio:
        asyncio.run(server.run_stdio())
    else:
        asyncio.run(main(args.port))
