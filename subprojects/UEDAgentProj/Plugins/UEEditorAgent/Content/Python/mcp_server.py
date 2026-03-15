"""
MCP WebSocket Server for UE Editor Agent
实现AI与UE编辑器之间的双向通信
"""

import asyncio
import json
import socket
import sys
from pathlib import Path
from typing import Optional, Dict, Any

import unreal
import websockets
from websockets.server import WebSocketServerProtocol

# 添加到 sys.path，确保可以导入自定义模块
plugin_root = Path(unreal.Paths.project_plugins_dir()) / "UEEditorAgent"
python_lib_path = plugin_root / "Content" / "Python" / "Lib"
if str(python_lib_path) not in sys.path:
    sys.path.insert(0, str(python_lib_path))


class MCPServer:
    """MCP WebSocket服务器，处理AI与UE编辑器之间的通信"""
    
    def __init__(self, host: str = "localhost", start_port: int = 8080):
        """
        初始化MCP服务器
        
        Args:
            host: 监听主机地址（默认localhost）
            start_port: 起始端口号（默认8080，如果占用则自动递增）
        """
        self.host = host
        self.start_port = start_port
        self.port = start_port
        self.server: Optional[websockets.WebSocketServer] = None
        self.is_running = False
        self.connected_client: Optional[WebSocketServerProtocol] = None
        self.reconnect_delay = 1.0  # 重连延迟（秒）
        
        # 存储服务器任务
        self.server_task: Optional[asyncio.Task] = None
        
    def find_available_port(self) -> int:
        """
        查找可用端口
        
        Returns:
            第一个可用的端口号
            
        Note:
            从 start_port 开始递增，最多尝试 100 个端口
        """
        port = self.start_port
        max_attempts = 100
        
        for _ in range(max_attempts):
            try:
                # 尝试绑定端口
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.host, port))
                sock.close()
                
                unreal.log(f"[MCPServer] 找到可用端口: {port}")
                return port
                
            except OSError:
                # 端口被占用，尝试下一个
                port += 1
                continue
                
        # 如果100个端口都不可用，使用起始端口并记录警告
        unreal.log_warning(f"[MCPServer] 未找到可用端口，使用默认端口: {self.start_port}")
        return self.start_port
    
    async def start(self):
        """启动WebSocket服务器"""
        if self.is_running:
            unreal.log_warning("[MCPServer] 服务器已在运行中")
            return
            
        # 查找可用端口
        self.port = self.find_available_port()
        
        try:
            # 启动WebSocket服务器
            self.server = await websockets.serve(
                self.connection_handler,
                self.host,
                self.port,
                ping_interval=20,  # 心跳间隔20秒
                ping_timeout=10,   # 心跳超时10秒
            )
            
            self.is_running = True
            unreal.log(f"[MCPServer] WebSocket服务器已启动: ws://{self.host}:{self.port}")
            unreal.log(f"[MCPServer] 等待AI客户端连接...")
            
            # 保存连接信息到Subsystem
            subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
            if subsystem:
                subsystem.set_server_port(self.port)
                subsystem.set_connection_status(False)  # 初始状态为未连接
            
            # 保持服务器运行
            await self.server.wait_closed()
            
        except Exception as e:
            unreal.log_error(f"[MCPServer] 启动服务器失败: {e}")
            self.is_running = False
            raise
    
    async def connection_handler(self, websocket: WebSocketServerProtocol, path: str):
        """
        处理WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
            path: 连接路径
        """
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        unreal.log(f"[MCPServer] AI客户端已连接: {client_info}")
        
        # 记录连接状态
        self.connected_client = websocket
        subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
        if subsystem:
            subsystem.set_connection_status(True)
        
        try:
            # 处理消息
            async for message in websocket:
                await self.handle_message(message)
                
        except websockets.exceptions.ConnectionClosed:
            unreal.log(f"[MCPServer] AI客户端断开连接: {client_info}")
        except Exception as e:
            unreal.log_error(f"[MCPServer] 处理消息时发生错误: {e}")
        finally:
            # 清理连接状态
            self.connected_client = None
            if subsystem:
                subsystem.set_connection_status(False)
            
            # 等待一段时间后允许重连
            await asyncio.sleep(self.reconnect_delay)
    
    async def handle_message(self, message: str):
        """
        处理接收到的消息
        
        Args:
            message: JSON格式的消息字符串
        """
        try:
            # 解析JSON消息
            data = json.loads(message)
            unreal.log(f"[MCPServer] 收到消息: {data}")
            
            # TODO: 实现MCP协议解析
            # 这里先简单回显消息
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "status": "received",
                    "message": f"UE Editor 已收到: {data.get('method', 'unknown')}"
                }
            }
            
            await self.send_response(response)
            
        except json.JSONDecodeError as e:
            unreal.log_error(f"[MCPServer] JSON解析失败: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                    "data": str(e)
                }
            }
            await self.send_response(error_response)
        
        except Exception as e:
            unreal.log_error(f"[MCPServer] 处理消息失败: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
            await self.send_response(error_response)
    
    async def send_response(self, response: Dict[str, Any]):
        """
        发送响应消息
        
        Args:
            response: 响应字典
        """
        if self.connected_client and self.connected_client.open:
            try:
                await self.connected_client.send(json.dumps(response))
                unreal.log(f"[MCPServer] 发送响应: {response}")
            except Exception as e:
                unreal.log_error(f"[MCPServer] 发送响应失败: {e}")
        else:
            unreal.log_warning("[MCPServer] 无可用连接，无法发送响应")
    
    async def stop(self):
        """停止WebSocket服务器"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # 关闭客户端连接
        if self.connected_client:
            await self.connected_client.close()
            self.connected_client = None
        
        # 关闭服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # 清理连接状态
        subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
        if subsystem:
            subsystem.set_connection_status(False)
            subsystem.set_server_port(0)
        
        unreal.log("[MCPServer] WebSocket服务器已停止")
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        获取服务器信息
        
        Returns:
            服务器信息字典
        """
        return {
            "host": self.host,
            "port": self.port,
            "is_running": self.is_running,
            "is_connected": self.connected_client is not None and self.connected_client.open,
            "reconnect_delay": self.reconnect_delay
        }


# 全局服务器实例
_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> Optional[MCPServer]:
    """获取全局MCP服务器实例"""
    return _mcp_server


def start_mcp_server(host: str = "localhost", port: int = 8080) -> bool:
    """
    启动MCP服务器
    
    Args:
        host: 监听主机地址
        port: 起始端口号
        
    Returns:
        成功返回True，失败返回False
    """
    global _mcp_server
    
    try:
        if _mcp_server is None:
            _mcp_server = MCPServer(host, port)
        
        # 检查是否已在运行
        if _mcp_server.is_running:
            unreal.log("[MCPServer] 服务器已在运行中")
            return True
        
        # 启动服务器（异步）
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 创建任务但不阻塞
        _mcp_server.server_task = loop.create_task(_mcp_server.start())
        
        unreal.log("[MCPServer] 正在启动服务器...")
        return True
        
    except Exception as e:
        unreal.log_error(f"[MCPServer] 启动失败: {e}")
        return False


def stop_mcp_server():
    """停止MCP服务器"""
    global _mcp_server
    
    if _mcp_server:
        try:
            # 获取事件循环
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # 异步停止服务器
            loop.run_until_complete(_mcp_server.stop())
            
        except Exception as e:
            unreal.log_error(f"[MCPServer] 停止失败: {e}")
        finally:
            _mcp_server = None
