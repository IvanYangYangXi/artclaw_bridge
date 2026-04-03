#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lobster_chat.py — LobsterAI Gateway 聊天桥接层
================================================

为 DCC (UE/Maya/Max) 提供 LobsterAI Gateway 的通信适配。
参考 openclaw_ws.py 实现，但适配 LobsterAI 的协议。

功能:
  - WebSocket 连接到 LobsterAI Gateway
  - 发送聊天消息
  - 接收流式回复
  - 通过 Qt signal/slot 或文件输出通知 UI

使用方式 (DCC 内嵌面板):
    from platforms.lobster.lobster_chat import LobsterChatManager
    manager = LobsterChatManager()
    manager.connect()
    manager.send_message("帮我创建立方体")

使用方式 (UE 文件轮询):
    python platforms/lobster/lobster_chat.py --message "hello" --output-dir "Saved/UEAgent/"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Optional, Callable, Dict, Any

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = 3
CLIENT_NAME = "dcc-lobster"
CLIENT_VERSION = "0.1.0"
CHAT_TIMEOUT = 1800.0  # 绝对超时 30 分钟
IDLE_TIMEOUT = 300.0   # 无活动超时 5 分钟
TOOL_RESULT_LIMIT = 2000

# LobsterAI Gateway 默认地址
DEFAULT_GATEWAY_URL = "ws://127.0.0.1:18790"
DEFAULT_GATEWAY_TOKEN = ""  # 从配置文件读取

logger = logging.getLogger("artclaw.lobster_chat")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _extract_text(message) -> str:
    """从消息中提取文本内容"""
    if isinstance(message, dict):
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        if isinstance(content, str):
            return content
        return message.get("text", "")
    if isinstance(message, str):
        return message
    return ""


def _truncate_for_debug(obj, max_str_len=200):
    """递归截断 JSON 对象中的长字符串"""
    if isinstance(obj, str):
        return obj[:max_str_len] + "..." if len(obj) > max_str_len else obj
    if isinstance(obj, dict):
        return {k: _truncate_for_debug(v, max_str_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate_for_debug(item, max_str_len) for item in obj[:20]]
    return obj


# ---------------------------------------------------------------------------
# 文件写入（UE 模式）
# ---------------------------------------------------------------------------

def write_stream(stream_file: str, obj: dict, lock: threading.Lock) -> None:
    """线程安全地向 stream.jsonl 追加一行"""
    try:
        line = json.dumps(obj, ensure_ascii=False)
        with lock:
            with open(stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as exc:
        logger.error(f"[lobster_chat] stream write: {exc}")


def write_response(response_file: str, text: str) -> None:
    """写入最终回复文件"""
    try:
        with open(response_file, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"[lobster_chat] response written ({len(text)} chars)")
    except Exception as exc:
        logger.error(f"[lobster_chat] response write: {exc}")


def write_bridge_status(status_dir: str, connected: bool, detail: str = "") -> None:
    """写入 _bridge_status.json"""
    try:
        import tempfile
        path = os.path.join(status_dir, "_bridge_status.json")
        data = {
            "timestamp": time.time(),
            "connected": connected,
            "detail": detail,
        }
        fd, tmp = tempfile.mkstemp(dir=status_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False))
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
    except Exception as exc:
        logger.error(f"[lobster_chat] write_bridge_status: {exc}")


# ---------------------------------------------------------------------------
# LobsterAI Chat Manager (Qt Signal 模式 - DCC 内嵌面板)
# ---------------------------------------------------------------------------

class LobsterChatSignals:
    """Qt signals for LobsterAI chat events"""
    
    def __init__(self):
        try:
            from PySide2.QtCore import QObject, Signal
            self._QObject = QObject
            # 连接状态变更
            self.connection_changed = Signal(bool, str)
            # 收到 AI 流式文本
            self.ai_message = Signal(str, str)
            # 工具调用
            self.tool_call = Signal(str, str, str)
            # 工具结果
            self.tool_result = Signal(str, str, str, bool)
            # 最终响应完成
            self.response_complete = Signal(str)
        except ImportError:
            self._QObject = None


class LobsterChatManager:
    """
    LobsterAI 聊天管理器 — 用于 DCC 内嵌面板
    
    使用:
        manager = LobsterChatManager()
        manager.connect()
        manager.send_message("hello")
    """
    
    _instance = None
    
    def __init__(self, gateway_url: str = DEFAULT_GATEWAY_URL, token: str = ""):
        self.gateway_url = gateway_url
        self.token = token
        self.session_key = ""
        self._ws = None
        self._connected = False
        self._lock = threading.Lock()
        self.signals = LobsterChatSignals() if LobsterChatSignals else None
        
        # 回调函数
        self.on_message: Optional[Callable[[str, str], None]] = None
        self.on_tool_call: Optional[Callable[[str, str, dict], None]] = None
        self.on_status: Optional[Callable[[bool, str], None]] = None
    
    @classmethod
    def instance(cls) -> "LobsterChatManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def connect(self) -> bool:
        """连接到 LobsterAI Gateway"""
        if self._connected:
            return True
        
        try:
            import websockets
        except ImportError:
            logger.error("websockets not installed")
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._do_connect())
            return self._connected
        except Exception as e:
            logger.error(f"Connect failed: {e}")
            return False
    
    async def _do_connect(self):
        """异步连接 Gateway"""
        import websockets
        
        try:
            self._ws = await websockets.connect(
                self.gateway_url,
                max_size=10 * 1024 * 1024,
                ping_interval=30,
                ping_timeout=10,
                open_timeout=10,
            )
            
            # 握手
            if await self._handshake():
                self._connected = True
                self.session_key = f"lobster-{uuid.uuid4()}"
                logger.info(f"Connected to LobsterAI Gateway: {self.session_key}")
                
                # 发送状态更新
                if self.on_status:
                    self.on_status(True, "Connected")
                if self.signals and self.signals._QObject:
                    self.signals.connection_changed.emit(True, "Connected")
            else:
                logger.error("Handshake failed")
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self._connected = False
    
    async def _handshake(self) -> bool:
        """握手并认证"""
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            msg = json.loads(raw)
            
            if msg.get("event") != "connect.challenge":
                return False
            
            req_id = str(uuid.uuid4())
            await self._ws.send(json.dumps({
                "type": "req", "id": req_id, "method": "connect",
                "params": {
                    "minProtocol": PROTOCOL_VERSION,
                    "maxProtocol": PROTOCOL_VERSION,
                    "client": {
                        "id": CLIENT_NAME,
                        "displayName": "DCC LobsterAI Bridge",
                        "version": CLIENT_VERSION,
                        "platform": sys.platform,
                        "mode": "dcc",
                    },
                    "caps": [],
                    "auth": {"token": self.token},
                    "role": "operator",
                    "scopes": ["operator.admin"],
                },
            }))
            
            deadline = time.time() + 10.0
            while time.time() < deadline:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
                msg = json.loads(raw)
                if msg.get("type") == "res" and msg.get("id") == req_id:
                    if msg.get("error"):
                        logger.error(f"Connect error: {msg['error']}")
                        return False
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Handshake error: {e}")
            return False
    
    def send_message(self, message: str) -> str:
        """
        发送消息并等待回复（阻塞）
        
        返回：最终回复文本
        """
        if not self._connected:
            logger.error("Not connected")
            return "[Error] Not connected"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._do_send_message(message))
    
    async def _do_send_message(self, message: str) -> str:
        """异步发送消息"""
        try:
            req_id = str(uuid.uuid4())
            await self._ws.send(json.dumps({
                "type": "req", "id": req_id,
                "method": "chat.send",
                "params": {
                    "sessionKey": self.session_key,
                    "message": message,
                    "idempotencyKey": str(uuid.uuid4()),
                },
            }))
            
            # 等待 ACK
            ack = await self._wait_for_ack(req_id, timeout=15.0)
            if ack is None:
                return "[Error] ACK timeout"
            
            status = ack.get("status", "")
            
            # 同步回复（不经过流）
            if status in ("started", "streaming", "accepted", "running"):
                # 流式回复，启动接收循环
                return await self._receive_stream()
            else:
                # 同步回复
                msg_text = _extract_text(ack.get("message", ""))
                if msg_text:
                    if self.on_message:
                        self.on_message("final", msg_text)
                    if self.signals and self.signals._QObject:
                        self.signals.ai_message.emit("final", msg_text)
                        self.signals.response_complete.emit(msg_text)
                    return msg_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return f"[Error] {e}"
    
    async def _wait_for_ack(self, req_id: str, timeout: float = 15.0) -> Optional[dict]:
        """等待 RPC 响应"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=min(deadline - time.time(), 5.0))
                msg = json.loads(raw)
                if msg.get("type") == "res" and msg.get("id") == req_id:
                    if msg.get("error"):
                        logger.error(f"Error: {msg['error']}")
                        return None
                    return msg.get("payload", {})
            except asyncio.TimeoutError:
                break
        
        return None
    
    async def _receive_stream(self) -> str:
        """接收流式回复"""
        latest_text = ""
        abs_deadline = time.time() + CHAT_TIMEOUT
        idle_deadline = time.time() + IDLE_TIMEOUT
        
        while True:
            now = time.time()
            if now >= abs_deadline or now >= idle_deadline:
                break
            
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=0.5)
                msg = json.loads(raw)
                
                if msg.get("event") != "chat":
                    continue
                
                payload = msg.get("payload", {})
                state = payload.get("state", "")
                
                # 更新空闲超时
                idle_deadline = time.time() + IDLE_TIMEOUT
                
                # 处理不同类型的消息
                if state == "delta":
                    delta_text = payload.get("delta", "")
                    latest_text += delta_text
                    if self.on_message:
                        self.on_message("delta", delta_text)
                    if self.signals and self.signals._QObject:
                        self.signals.ai_message.emit("delta", delta_text)
                
                elif state == "final":
                    final_text = _extract_text(payload.get("message", ""))
                    if final_text:
                        latest_text = final_text
                    if self.on_message:
                        self.on_message("final", latest_text)
                    if self.signals and self.signals._QObject:
                        self.signals.ai_message.emit("final", latest_text)
                        self.signals.response_complete.emit(latest_text)
                    return latest_text
                
                elif state == "error":
                    error_text = _extract_text(payload.get("message", ""))
                    if self.on_message:
                        self.on_message("error", error_text or "[Error]")
                    if self.signals and self.signals._QObject:
                        self.signals.ai_message.emit("error", error_text or "[Error]")
                    return error_text or "[Error]"
                
                elif state == "aborted":
                    if self.on_message:
                        self.on_message("aborted", "[Aborted]")
                    if self.signals and self.signals._QObject:
                        self.signals.ai_message.emit("aborted", "[Aborted]")
                    return "[Aborted]"
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Receive error: {e}")
                return f"[Error] Connection lost: {e}"
        
        return latest_text
    
    def disconnect(self):
        """断开连接"""
        self._connected = False
        if self._ws:
            asyncio.get_event_loop().run_until_complete(self._ws.close())
            self._ws = None
        
        if self.on_status:
            self.on_status(False, "Disconnected")
        if self.signals and self.signals._QObject:
            self.signals.connection_changed.emit(False, "Disconnected")
    
    def is_connected(self) -> bool:
        return self._connected


# ---------------------------------------------------------------------------
# CLI 入口（UE 文件轮询模式）
# ---------------------------------------------------------------------------

def main():
    """CLI 入口 — 用于测试或 UE 文件轮询模式"""
    parser = argparse.ArgumentParser(description="LobsterAI Chat Bridge")
    parser.add_argument("--message", type=str, default="Hello", help="消息内容")
    parser.add_argument("--gateway", type=str, default=DEFAULT_GATEWAY_URL, help="Gateway URL")
    parser.add_argument("--token", type=str, default="", help="Gateway Token")
    parser.add_argument("--output-dir", type=str, default="", help="输出目录（UE 模式）")
    
    args = parser.parse_args()
    
    # UE 文件轮询模式
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        stream_file = os.path.join(args.output_dir, "_lobster_response_stream.jsonl")
        response_file = os.path.join(args.output_dir, "_lobster_response.txt")
        status_file = os.path.join(args.output_dir, "_bridge_status.json")
        
        lock = threading.Lock()
        
        # 写入初始状态
        write_bridge_status(args.output_dir, True, "Connecting...")
        
        # 创建管理器
        manager = LobsterChatManager(gateway_url=args.gateway, token=args.token)
        
        if manager.connect():
            write_bridge_status(args.output_dir, True, "Connected")
            
            # 发送消息
            response = manager.send_message(args.message)
            
            # 写入响应
            write_stream(stream_file, {"type": "final", "text": response}, lock)
            write_response(response_file, response)
            
            write_bridge_status(args.output_dir, True, "Completed")
            manager.disconnect()
        else:
            write_bridge_status(args.output_dir, False, "Connection failed")
            write_response(response_file, "[Error] Connection failed")
    else:
        # 交互模式
        print(f"Connecting to {args.gateway}...")
        manager = LobsterChatManager(gateway_url=args.gateway, token=args.token)
        
        if manager.connect():
            print("Connected! Type 'quit' to exit.")
            while True:
                msg = input("\nYou: ").strip()
                if msg.lower() in ("quit", "exit"):
                    break
                print("AI: ", end="", flush=True)
                response = manager.send_message(msg)
                print(response)
            manager.disconnect()
        else:
            print("Connection failed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
