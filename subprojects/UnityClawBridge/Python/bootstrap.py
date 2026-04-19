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
from pathlib import Path

# sys.path 回溯：开发模式下加载 core/
_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent  # UnityClawBridge/
_ARTCLAW_ROOT = None

if "ARTCLAW_PROJECT_ROOT" in os.environ:
    _ARTCLAW_ROOT = Path(os.environ["ARTCLAW_PROJECT_ROOT"])
else:
    _ARTCLAW_ROOT = _PLUGIN_ROOT.parent.parent  # 向上 4 级

for _p in [str(_ARTCLAW_ROOT), str(_ARTCLAW_ROOT / "core")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="[ArtClaw|Unity] %(levelname)s %(message)s",
)
logger = logging.getLogger("artclaw.unity")


# ════════════════════════════════════════
# Unity HTTP 命令通道客户端
# ════════════════════════════════════════

class UnityCommandChannel:
    """
    与 Unity C# 端 HTTP 命令服务器交互。

    C# 端（CommandServer.cs）监听 http://127.0.0.1:8089
    - POST /execute  { "id": "uuid", "code": "..." } → {"queued": true}
    - GET  /result/{id}                              → {"done": bool, "result": ..., "error": ...}
    - GET  /health                                   → {"status": "ok", "unity_version": ...}
    - GET  /logs                                     → {"logs": [...]}
    - POST /validate { "code": "..." }                → {"valid": bool, "errors": [...]}
    """

    def __init__(self, unity_http_port: int = 8089):
        self.base_url = f"http://127.0.0.1:{unity_http_port}"
        self._timeout = 60.0

    async def execute_code(self, code: str) -> dict:
        """向 Unity C# 端提交代码，阻塞等待执行结果"""
        import aiohttp
        import uuid

        exec_id = str(uuid.uuid4())
        payload = {"id": exec_id, "code": code}

        async with aiohttp.ClientSession() as session:
            # 1. 提交代码
            async with session.post(
                f"{self.base_url}/execute",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    return {"success": False, "error": f"命令提交失败: HTTP {resp.status} - {body}"}

            # 2. 轮询结果
            deadline = time.time() + self._timeout
            while time.time() < deadline:
                await asyncio.sleep(0.05)
                async with session.get(
                    f"{self.base_url}/result/{exec_id}",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("done"):
                            return {
                                "success": data.get("success", True),
                                "result": data.get("result"),
                                "error": data.get("error"),
                                "output": data.get("output", ""),
                            }

            return {"success": False, "error": f"执行超时（{self._timeout}s）"}

    async def validate_code(self, code: str) -> dict:
        """语法预验证"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/validate",
                json={"code": code},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"valid": False, "errors": [{"message": f"HTTP {resp.status}"}]}

    async def get_health(self) -> dict:
        """获取健康状态"""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {"status": "unavailable"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_logs(self) -> dict:
        """获取执行日志"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/logs",
                timeout=aiohttp.ClientTimeout(total=3),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"logs": []}


# ════════════════════════════════════════
# MCP 工具处理器
# ════════════════════════════════════════

_command_channel = UnityCommandChannel()


async def run_unity_python_handler(arguments: dict) -> dict:
    """
    MCP 工具 run_unity_python 的处理器。

    Args:
        arguments: {"code": "C# 代码字符串"}

    Returns:
        {"content": [{"type": "text", "text": "..."}], "isError": bool}
    """
    code = arguments.get("code", "")
    if not code.strip():
        return {"content": [{"type": "text", "text": "错误: code 参数为空"}], "isError": True}

    result = await _command_channel.execute_code(code)

    if result.get("success"):
        output = result.get("output") or ""
        res = result.get("result")
        if res:
            if isinstance(res, str):
                output = output + "\n" + res if output else res
            else:
                output = output + "\n" + json.dumps(res, ensure_ascii=False, indent=2) if output else json.dumps(res, ensure_ascii=False, indent=2)
        return {"content": [{"type": "text", "text": output or "执行完成（无输出）"}]}
    else:
        error_msg = result.get("error", "未知错误")
        return {"content": [{"type": "text", "text": f"执行失败: {error_msg}"}], "isError": True}


async def validate_script_handler(arguments: dict) -> dict:
    """MCP 工具 validate_script 的处理器"""
    code = arguments.get("code", "")
    if not code.strip():
        return {"content": [{"type": "text", "text": "错误: code 参数为空"}], "isError": True}

    result = await _command_channel.validate_code(code)
    if result.get("valid"):
        return {"content": [{"type": "text", "text": "语法验证通过"}]}
    else:
        errors = result.get("errors", [])
        msg = "语法错误：\n" + "\n".join([f"  - {e.get('message')}" for e in errors])
        return {"content": [{"type": "text", "text": msg}], "isError": True}


async def unity_health_handler(arguments: dict) -> dict:
    """MCP 工具 unity_health 的处理器"""
    health = await _command_channel.get_health()
    status = health.get("status", "unknown")
    if status == "ok":
        info = [
            f"Unity 版本: {health.get('unity_version')}",
            f"项目: {health.get('project_name')}",
            f"播放状态: {'播放中' if health.get('is_playing') else '暂停'}",
            f"编译状态: {'编译中' if health.get('is_compiling') else '就绪'}",
            f"执行计数: {health.get('execution_count', 0)}",
        ]
        return {"content": [{"type": "text", "text": "\n".join(info)}]}
    else:
        return {"content": [{"type": "text", "text": f"Unity 不可用: {status}"}], "isError": True}


async def unity_logs_handler(arguments: dict) -> dict:
    """MCP 工具 unity_logs 的处理器"""
    logs = await _command_channel.get_logs()
    entries = logs.get("logs", [])
    if not entries:
        return {"content": [{"type": "text", "text": "无执行日志"}]}

    lines = []
    for e in entries[-20:]:  # 最近 20 条
        icon = "OK" if e.get("success") else "FAIL"
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


# ════════════════════════════════════════
# MCP Server 启动
# ════════════════════════════════════════

async def main(port: int):
    """主入口：启动 MCP WebSocket Server"""
    logger.info(f"UnityClawBridge MCP Server 启动中... 端口={port}")

    try:
        from mcp_server import MCPServer
    except ImportError as e:
        logger.error(f"共享 MCPServer 不可用: {e}")
        return

    server = MCPServer(host="127.0.0.1", port=port)

    # 注册工具
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
        main_thread=False,
    )

    server.register_tool(
        name="validate_script",
        description="Validate C# code syntax without executing. Use before running complex scripts to catch errors early.",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "C# code to validate"}
            },
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
    logger.info(f"MCP Server 启动 ws://127.0.0.1:{port}")
    logger.info("等待 AI 客户端连接...")

    await server._run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UnityClawBridge MCP Server")
    parser.add_argument("--port", type=int, default=8088, help="MCP Server WebSocket 端口")
    parser.add_argument("--plugin-root", type=str, default="", help="插件根目录")
    args = parser.parse_args()

    if args.plugin_root:
        _PLUGIN_ROOT = Path(args.plugin_root)
        _ARTCLAW_ROOT = _PLUGIN_ROOT.parent.parent
        sys.path.insert(0, str(_ARTCLAW_ROOT))
        sys.path.insert(0, str(_ARTCLAW_ROOT / "core"))

    asyncio.run(main(args.port))
