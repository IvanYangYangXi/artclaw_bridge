"""
bridge_diagnostics.py - OpenClaw Gateway 连接诊断
==================================================

平台无关。逐项检查 Gateway 连接问题。
"""

from __future__ import annotations

import asyncio
import json
import socket
import time
import urllib.parse
import uuid
from typing import Optional

from bridge_config import (
    DEFAULT_TOKEN,
    PROTOCOL_VERSION,
    CLIENT_NAME,
    CLIENT_VERSION,
    load_config,
)


# Gateway 允许的 client.id 白名单
_VALID_CLIENT_IDS = {
    "webchat-ui", "openclaw-control-ui", "webchat", "cli",
    "gateway-client", "openclaw-macos", "openclaw-ios",
    "openclaw-android", "node-host", "test", "fingerprint",
    "openclaw-probe",
}


def diagnose_connection(
    gateway_url: str = "",
    token: str = "",
    logger=None,
) -> str:
    """
    诊断 OpenClaw Gateway 连接，逐项检查所有已知问题。

    Returns:
        多行诊断报告文本
    """
    config = load_config()
    gw_config = config.get("gateway", {})
    url = gateway_url or f"ws://127.0.0.1:{gw_config.get('port', 18789)}"
    tok = token or gw_config.get("auth", {}).get("token", DEFAULT_TOKEN)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  OpenClaw Gateway 连接诊断")
    lines.append("=" * 60)
    errors = 0
    warnings = 0

    # ── 检查 1: websockets 包 ──
    lines.append("\n[1/6] websockets 包...")
    try:
        import websockets
        lines.append(f"  ✅ websockets {websockets.__version__} 已安装")
    except ImportError:
        lines.append("  ❌ websockets 未安装!")
        lines.append("     修复: pip install websockets")
        errors += 1

    # ── 检查 2: Gateway URL 格式 ──
    lines.append("\n[2/6] Gateway URL...")
    lines.append(f"  目标: {url}")
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 18789
    if parsed.scheme not in ("ws", "wss"):
        lines.append(f"  ❌ URL scheme 应为 ws:// 或 wss://，当前: {parsed.scheme}://")
        errors += 1
    else:
        lines.append(f"  ✅ scheme={parsed.scheme}, host={host}, port={port}")

    # ── 检查 3: TCP 端口可达 ──
    lines.append("\n[3/6] TCP 端口可达性...")
    try:
        sock = socket.create_connection((host, port), timeout=3.0)
        sock.close()
        lines.append(f"  ✅ {host}:{port} 可达")
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        lines.append(f"  ❌ {host}:{port} 不可达: {e}")
        lines.append("     可能原因: OpenClaw 未启动，或端口被占用")
        lines.append("     修复: 运行 openclaw start")
        errors += 1

    # ── 检查 4: Auth Token ──
    lines.append("\n[4/6] Auth Token...")
    if tok:
        masked = tok[:8] + "..." + tok[-4:] if len(tok) > 12 else "***"
        lines.append(f"  ✅ Token 已配置: {masked}")
        file_token = gw_config.get("auth", {}).get("token", "")
        if file_token and tok == file_token:
            lines.append("  ℹ️  来源: ~/.openclaw/openclaw.json")
        elif tok == DEFAULT_TOKEN:
            lines.append("  ⚠️  来源: 硬编码默认值 (建议从 openclaw.json 读取)")
            warnings += 1
    else:
        lines.append("  ❌ Token 为空!")
        lines.append("     修复: 检查 ~/.openclaw/openclaw.json 中的 gateway.auth.token")
        errors += 1

    # ── 检查 5: Client ID 白名单 ──
    lines.append("\n[5/6] Client ID 白名单校验...")
    lines.append(f'  client.id = "{CLIENT_NAME}"')
    lines.append(f'  client.mode = "cli"')
    if CLIENT_NAME in _VALID_CLIENT_IDS:
        lines.append("  ✅ client.id 在白名单中")
    else:
        lines.append(f'  ❌ client.id "{CLIENT_NAME}" 不在白名单中!')
        lines.append(f"     允许值: {', '.join(sorted(_VALID_CLIENT_IDS))}")
        errors += 1

    # ── 检查 6: WebSocket 握手测试 ──
    lines.append("\n[6/6] WebSocket 握手测试...")
    if errors > 0:
        lines.append("  ⏭️  跳过 (前置检查有错误)")
    else:
        try:
            result = asyncio.run(_diagnose_handshake(url, tok))
            for line in result:
                lines.append(f"  {line}")
        except Exception as e:
            lines.append(f"  ❌ 握手测试异常: {e}")
            errors += 1

    # ── 汇总 ──
    lines.append("\n" + "=" * 60)
    if errors == 0 and warnings == 0:
        lines.append("  🎉 所有检查通过! Gateway 连接应该正常工作。")
    elif errors == 0:
        lines.append(f"  ⚠️  通过，但有 {warnings} 个警告。")
    else:
        lines.append(f"  ❌ 发现 {errors} 个错误，{warnings} 个警告。请按上述提示修复。")
    lines.append("=" * 60)

    report = "\n".join(lines)

    # 输出到日志
    if logger:
        for line in lines:
            stripped = line.strip()
            if stripped:
                if "❌" in stripped:
                    logger.error(f"[Diagnose] {stripped}")
                elif "⚠️" in stripped:
                    logger.warning(f"[Diagnose] {stripped}")
                elif "✅" in stripped or "🎉" in stripped:
                    logger.info(f"[Diagnose] {stripped}")

    return report


async def _diagnose_handshake(url: str, token: str) -> list[str]:
    """执行 WebSocket 连接 + 握手测试"""
    import websockets

    results: list[str] = []
    try:
        async with websockets.connect(url, open_timeout=5.0) as ws:
            results.append("✅ WebSocket 连接成功")

            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            msg = json.loads(raw)
            if msg.get("event") == "connect.challenge":
                nonce = msg.get("payload", {}).get("nonce", "")
                results.append(f"✅ 收到 challenge (nonce={nonce[:8]}...)")
            else:
                results.append(
                    f"⚠️  期望 connect.challenge，收到: "
                    f"{msg.get('event', msg.get('type', '?'))}"
                )
                return results

            connect_frame = {
                "type": "req",
                "id": str(uuid.uuid4()),
                "method": "connect",
                "params": {
                    "minProtocol": PROTOCOL_VERSION,
                    "maxProtocol": PROTOCOL_VERSION,
                    "client": {
                        "id": CLIENT_NAME,
                        "displayName": "UE Agent Diagnose",
                        "version": CLIENT_VERSION,
                        "platform": "win32",
                        "mode": "cli",
                    },
                    "caps": [],
                    "auth": {"token": token},
                    "role": "operator",
                    "scopes": ["operator.admin"],
                },
            }
            await ws.send(json.dumps(connect_frame))

            deadline = time.time() + 5.0
            while time.time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                msg = json.loads(raw)
                if (
                    msg.get("type") == "res"
                    and msg.get("id") == connect_frame["id"]
                ):
                    if msg.get("error"):
                        err = msg["error"]
                        results.append(
                            f"❌ 握手被拒绝: "
                            f"{err.get('code', '?')}: {err.get('message', '?')}"
                        )
                        err_msg = err.get("message", "")
                        if "client/id" in err_msg:
                            results.append(
                                f'   原因: client.id "{CLIENT_NAME}" 不被接受'
                            )
                        elif "auth" in err_msg.lower() or "token" in err_msg.lower():
                            results.append("   原因: Token 无效或过期")
                    else:
                        results.append("✅ 握手成功! (helloOk)")
                    return results

            results.append("⚠️  等待 connect 响应超时 (5s)")

    except asyncio.TimeoutError:
        results.append("❌ 超时: Gateway 没有响应")
    except ConnectionRefusedError:
        results.append("❌ 连接被拒绝: Gateway 可能未启动")
    except Exception as e:
        results.append(f"❌ 异常: {type(e).__name__}: {e}")

    return results
