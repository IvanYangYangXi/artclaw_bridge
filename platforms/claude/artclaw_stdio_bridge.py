#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw stdio→WebSocket MCP 桥接器
====================================

将 stdio MCP 请求转发到 ArtClaw 的 WebSocket MCP Server。
供 Claude Desktop、Cursor 等仅支持 stdio 传输的 MCP 客户端使用。

用法:
    python artclaw_stdio_bridge.py                    # 默认连接 ws://127.0.0.1:8080
    python artclaw_stdio_bridge.py --port 8081        # 连接 Maya MCP Server
    python artclaw_stdio_bridge.py --url ws://host:port  # 自定义 URL

Claude Desktop 配置示例 (claude_desktop_config.json):
    {
      "mcpServers": {
        "artclaw-ue": {
          "command": "python",
          "args": ["C:/path/to/artclaw_stdio_bridge.py", "--port", "8080"]
        }
      }
    }
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import logging

# ---------------------------------------------------------------------------
# 日志（必须写到 stderr，stdout 保留给 MCP 协议）
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("artclaw-stdio-bridge")


# ---------------------------------------------------------------------------
# stdio 读写
# ---------------------------------------------------------------------------

async def read_stdin_line(reader: asyncio.StreamReader) -> str | None:
    """从 stdin 读取一行 JSON-RPC 消息（换行分隔）"""
    try:
        line = await reader.readline()
        if not line:
            return None
        return line.decode("utf-8").strip()
    except Exception as e:
        log.error("stdin 读取失败: %s", e)
        return None


def write_stdout(data: str):
    """将 JSON-RPC 消息写到 stdout（换行分隔）"""
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# WebSocket 连接管理
# ---------------------------------------------------------------------------

async def connect_ws(url: str, max_retries: int = 5, retry_delay: float = 2.0):
    """连接 WebSocket MCP Server，带重试"""
    try:
        import websockets
    except ImportError:
        log.error("需要安装 websockets: pip install websockets")
        sys.exit(1)

    for attempt in range(1, max_retries + 1):
        try:
            ws = await websockets.connect(url)
            log.info("已连接到 MCP Server: %s", url)
            return ws
        except Exception as e:
            if attempt < max_retries:
                log.warning(
                    "连接失败 (尝试 %d/%d): %s — %s 秒后重试",
                    attempt, max_retries, e, retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                log.error("连接失败，已达最大重试次数: %s", e)
                raise


# ---------------------------------------------------------------------------
# 核心桥接循环
# ---------------------------------------------------------------------------

async def bridge_loop(ws_url: str):
    """
    主循环：
    1. stdin → 读 JSON-RPC 请求
    2. → 转发到 WebSocket MCP Server
    3. ← 接收响应
    4. → 写到 stdout
    """
    ws = await connect_ws(ws_url)
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    try:
        while True:
            line = await read_stdin_line(reader)
            if line is None:
                log.info("stdin 已关闭，退出")
                break

            if not line:
                continue

            # 验证是 JSON
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                log.warning("无效 JSON: %s", e)
                continue

            log.debug("→ MCP Server: %s", line[:200])

            # 转发到 WebSocket
            try:
                await ws.send(line)
            except Exception as e:
                log.error("WebSocket 发送失败: %s — 尝试重连", e)
                try:
                    ws = await connect_ws(ws_url)
                    await ws.send(line)
                except Exception as e2:
                    log.error("重连后仍失败: %s", e2)
                    # 返回 JSON-RPC 错误
                    if "id" in msg:
                        err_resp = {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "error": {
                                "code": -32000,
                                "message": f"WebSocket 连接失败: {e2}",
                            },
                        }
                        write_stdout(json.dumps(err_resp))
                    continue

            # 接收响应
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=300)
                log.debug("← MCP Server: %s", response[:200])
                write_stdout(response)
            except asyncio.TimeoutError:
                log.error("等待 MCP Server 响应超时 (300s)")
                if "id" in msg:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": msg["id"],
                        "error": {
                            "code": -32000,
                            "message": "MCP Server 响应超时",
                        },
                    }
                    write_stdout(json.dumps(err_resp))
            except Exception as e:
                log.error("接收响应失败: %s", e)
                if "id" in msg:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": msg["id"],
                        "error": {
                            "code": -32000,
                            "message": f"接收响应失败: {e}",
                        },
                    }
                    write_stdout(json.dumps(err_resp))

    finally:
        try:
            await ws.close()
        except Exception:
            pass
        log.info("桥接器已退出")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ArtClaw stdio→WebSocket MCP 桥接器",
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="DCC MCP Server 端口 (默认: 8080=UE, 8081=Maya, 8082=Max)",
    )
    parser.add_argument(
        "--url", type=str, default="",
        help="自定义 WebSocket URL (优先于 --port)",
    )
    args = parser.parse_args()

    ws_url = args.url or f"ws://127.0.0.1:{args.port}"
    log.info("ArtClaw stdio Bridge 启动 — 目标: %s", ws_url)

    try:
        asyncio.run(bridge_loop(ws_url))
    except KeyboardInterrupt:
        log.info("用户中断")
    except Exception as e:
        log.error("致命错误: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
