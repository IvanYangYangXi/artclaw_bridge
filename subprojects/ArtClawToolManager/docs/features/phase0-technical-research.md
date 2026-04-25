# Phase 0: 技术预研详细文档

> **版本**: 1.0
> **日期**: 2026-04-10
> **状态**: 规划阶段
> **目标**: 验证关键技术方案，降低后续开发风险

---

## 目录

1. [技术预研概述](#1-技术预研概述)
2. [预研任务清单](#2-预研任务清单)
3. [DCC 通信方案验证](#3-dcc-通信方案验证)
4. [OpenClaw Gateway 集成验证](#4-openclaw-gateway-集成验证)
5. [对话面板技术方案验证](#5-对话面板技术方案验证)
6. [数据存储方案选择](#6-数据存储方案选择)
7. [风险评估与应对方案](#7-风险评估与应对方案)
8. [预研结果文档化要求](#8-预研结果文档化要求)
9. [时间计划](#9-时间计划)

---

## 1. 技术预研概述

### 1.1 预研目标

Phase 0 技术预研旨在验证 ArtClaw Tool Manager 项目中的关键技术方案，确保后续开发阶段的技术可行性，并提前识别和解决潜在风险。

### 1.2 预研范围

| 序号 | 技术领域 | 预研内容 | 优先级 |
|------|----------|----------|--------|
| 1 | DCC 通信 | WebSocket vs HTTP 方案对比与验证 | P0 |
| 2 | Gateway 集成 | OpenClaw Gateway 转发机制验证 | P0 |
| 3 | 前端技术 | 对话面板技术方案验证 | P0 |
| 4 | 数据存储 | JSON vs SQLite 方案选择 | P1 |

### 1.3 预期产出

- 技术验证报告（本文档）
- 关键技术 POC 代码
- 风险评估和应对方案
- 技术选型决策记录

---

## 2. 预研任务清单

### 2.1 任务总览

```
Phase 0 (3-5天)
│
├── Day 1-2: DCC 通信方案验证
│   ├── 2.1 WebSocket 通信验证
│   ├── 2.2 HTTP 通信验证
│   ├── 2.3 混合方案设计
│   └── 2.4 性能对比测试
│
├── Day 2-3: OpenClaw Gateway 集成验证
│   ├── 3.1 Gateway 连接验证
│   ├── 3.2 MCP Bridge 通信验证
│   ├── 3.3 多 DCC 并发测试
│   └── 3.4 消息转发链路验证
│
├── Day 3-4: 对话面板技术方案验证
│   ├── 4.1 WebSocket 实时通信
│   ├── 4.2 消息流渲染性能
│   ├── 4.3 右侧面板动态表单
│   └── 4.4 状态管理方案
│
└── Day 4-5: 数据存储方案选择
    ├── 5.1 JSON 文件方案验证
    ├── 5.2 SQLite 方案验证
    ├── 5.3 混合存储方案设计
    └── 5.4 性能基准测试
```

### 2.2 验收标准

每项技术验证必须满足以下验收标准：

| 验证项 | 验收标准 | 测试方法 |
|--------|----------|----------|
| DCC 通信 | 延迟 < 100ms，连接稳定 | 压力测试 |
| Gateway 集成 | 消息转发成功率 > 99.9% | 端到端测试 |
| 对话面板 | 消息渲染流畅，无卡顿 | 性能测试 |
| 数据存储 | 读写性能满足需求 | 基准测试 |

---

## 3. DCC 通信方案验证

### 3.1 方案对比

#### 3.1.1 WebSocket 方案

**优点**:
- 全双工通信，支持实时双向数据流
- 低延迟，适合高频交互场景
- 连接状态保持，减少握手开销
- 支持服务器推送（进度更新、事件通知）

**缺点**:
- 需要维护长连接，增加复杂度
- 防火墙/NAT 环境可能需要额外配置
- 断线重连逻辑需要额外实现

**适用场景**:
- 实时对话交互
- 进度推送（Workflow 执行进度）
- 事件订阅（DCC 状态变更）

#### 3.1.2 HTTP 方案

**优点**:
- 简单易用，广泛支持
- 无状态，易于水平扩展
- 防火墙友好
- 成熟的缓存和负载均衡支持

**缺点**:
- 半双工，需要轮询获取更新
- 每次请求都有握手开销
- 不适合高频实时场景

**适用场景**:
- 配置读取/写入
- 静态资源获取
- 低频控制命令

#### 3.1.3 推荐方案：WebSocket + HTTP 混合

基于 ArtClaw Tool Manager 的需求分析，推荐采用 **WebSocket 为主、HTTP 为辅** 的混合方案：

| 通信类型 | 协议 | 用途 |
|----------|------|------|
| 实时对话 | WebSocket | AI 对话消息流 |
| 进度推送 | WebSocket | Workflow 执行进度 |
| 状态同步 | WebSocket | DCC 连接状态 |
| 配置管理 | HTTP | 工具配置 CRUD |
| 文件传输 | HTTP | 图片/工作流文件上传下载 |
| 静态资源 | HTTP | 预览图、文档 |

### 3.2 WebSocket 通信验证

#### 3.2.1 验证目标

验证 WebSocket 在以下场景的可行性：
1. 与 UE/Maya/ComfyUI 等 DCC 的 WebSocket 连接
2. 高并发消息传输性能
3. 断线重连稳定性
4. 跨平台兼容性

#### 3.2.2 验证环境

```yaml
测试环境:
  - OS: Windows 10/11
  - Python: 3.10+
  - Node.js: 18+
  
测试目标:
  - UE 5.7 (port: 8080)
  - Maya 2024 (port: 8081)
  - ComfyUI (port: 8087)
```

#### 3.2.3 验证代码

**POC 1: 基础 WebSocket 连接测试**

```python
# test_websocket_basic.py
"""WebSocket 基础连接测试"""

import asyncio
import websockets
import json
import time
from typing import Optional

class WebSocketClient:
    """WebSocket 客户端测试类"""
    
    def __init__(self, uri: str, name: str):
        self.uri = uri
        self.name = name
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.messages_received = 0
        self.latencies = []
        
    async def connect(self) -> bool:
        """建立 WebSocket 连接"""
        try:
            self.websocket = await websockets.connect(self.uri)
            self.connected = True
            print(f"[{self.name}] Connected to {self.uri}")
            return True
        except Exception as e:
            print(f"[{self.name}] Connection failed: {e}")
            return False
    
    async def send_message(self, message: dict) -> bool:
        """发送消息"""
        if not self.websocket:
            return False
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            print(f"[{self.name}] Send failed: {e}")
            return False
    
    async def receive_messages(self, duration: int = 10):
        """接收消息并计算延迟"""
        start_time = time.time()
        try:
            while time.time() - start_time < duration:
                message = await asyncio.wait_for(
                    self.websocket.recv(), 
                    timeout=1.0
                )
                receive_time = time.time()
                data = json.loads(message)
                
                # 计算延迟（如果消息包含发送时间戳）
                if 'timestamp' in data:
                    latency = (receive_time - data['timestamp']) * 1000
                    self.latencies.append(latency)
                
                self.messages_received += 1
                print(f"[{self.name}] Received: {data.get('type', 'unknown')}")
                
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"[{self.name}] Receive error: {e}")
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            print(f"[{self.name}] Disconnected")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        if self.latencies:
            avg_latency = sum(self.latencies) / len(self.latencies)
            max_latency = max(self.latencies)
            min_latency = min(self.latencies)
        else:
            avg_latency = max_latency = min_latency = 0
            
        return {
            'name': self.name,
            'connected': self.connected,
            'messages_received': self.messages_received,
            'avg_latency_ms': round(avg_latency, 2),
            'max_latency_ms': round(max_latency, 2),
            'min_latency_ms': round(min_latency, 2),
        }


async def test_single_connection():
    """测试单个 WebSocket 连接"""
    print("=" * 50)
    print("Test: Single WebSocket Connection")
    print("=" * 50)
    
    # 测试 ComfyUI 连接（假设已启动）
    client = WebSocketClient("ws://localhost:8087", "ComfyUI")
    
    # 连接
    success = await client.connect()
    if not success:
        print("❌ Connection test FAILED")
        return False
    
    # 发送测试消息
    test_msg = {
        'type': 'ping',
        'timestamp': time.time()
    }
    await client.send_message(test_msg)
    
    # 接收响应
    await client.receive_messages(duration=5)
    
    # 断开
    await client.disconnect()
    
    # 输出统计
    stats = client.get_stats()
    print(f"\n📊 Statistics:")
    print(f"  Messages received: {stats['messages_received']}")
    print(f"  Average latency: {stats['avg_latency_ms']}ms")
    
    print("✅ Single connection test PASSED")
    return True


async def test_multiple_connections():
    """测试多个并发 WebSocket 连接"""
    print("\n" + "=" * 50)
    print("Test: Multiple Concurrent Connections")
    print("=" * 50)
    
    clients = [
        WebSocketClient("ws://localhost:8080", "UE"),
        WebSocketClient("ws://localhost:8081", "Maya"),
        WebSocketClient("ws://localhost:8087", "ComfyUI"),
    ]
    
    # 并行连接
    connect_tasks = [c.connect() for c in clients]
    results = await asyncio.gather(*connect_tasks, return_exceptions=True)
    
    connected_count = sum(1 for r in results if r is True)
    print(f"Connected: {connected_count}/{len(clients)}")
    
    # 并行发送消息
    send_tasks = []
    for client in clients:
        if client.connected:
            msg = {
                'type': 'ping',
                'timestamp': time.time()
            }
            send_tasks.append(client.send_message(msg))
    
    await asyncio.gather(*send_tasks, return_exceptions=True)
    
    # 并行接收
    receive_tasks = [c.receive_messages(duration=3) for c in clients if c.connected]
    await asyncio.gather(*receive_tasks, return_exceptions=True)
    
    # 断开所有连接
    disconnect_tasks = [c.disconnect() for c in clients]
    await asyncio.gather(*disconnect_tasks, return_exceptions=True)
    
    # 输出统计
    print("\n📊 Statistics:")
    for client in clients:
        stats = client.get_stats()
        status = "✅" if stats['connected'] else "❌"
        print(f"  {status} {stats['name']}: {stats['messages_received']} msgs, "
              f"avg {stats['avg_latency_ms']}ms")
    
    print("✅ Multiple connections test PASSED")
    return connected_count > 0


async def test_reconnection():
    """测试断线重连"""
    print("\n" + "=" * 50)
    print("Test: Reconnection Stability")
    print("=" * 50)
    
    client = WebSocketClient("ws://localhost:8087", "ComfyUI")
    
    for i in range(3):
        print(f"\n--- Attempt {i+1} ---")
        
        # 连接
        success = await client.connect()
        if not success:
            print(f"❌ Connection attempt {i+1} failed")
            continue
        
        # 发送消息
        await client.send_message({'type': 'ping', 'timestamp': time.time()})
        await asyncio.sleep(1)
        
        # 模拟断线
        await client.disconnect()
        await asyncio.sleep(0.5)
    
    print("\n✅ Reconnection test PASSED")
    return True


# 运行测试
if __name__ == "__main__":
    async def run_all_tests():
        await test_single_connection()
        await test_multiple_connections()
        await test_reconnection()
    
    asyncio.run(run_all_tests())
```

**POC 2: WebSocket 压力测试**

```python
# test_websocket_stress.py
"""WebSocket 压力测试"""

import asyncio
import websockets
import json
import time
import statistics
from concurrent.futures import ThreadPoolExecutor


class StressTestClient:
    """压力测试客户端"""
    
    def __init__(self, client_id: int, uri: str):
        self.client_id = client_id
        self.uri = uri
        self.latencies = []
        self.errors = 0
        self.messages_sent = 0
        self.messages_received = 0
        
    async def run(self, message_count: int = 100):
        """运行压力测试"""
        try:
            async with websockets.connect(self.uri) as ws:
                for i in range(message_count):
                    # 发送消息
                    send_time = time.time()
                    message = {
                        'type': 'echo',
                        'id': i,
                        'timestamp': send_time,
                        'payload': 'x' * 1000  # 1KB payload
                    }
                    
                    try:
                        await ws.send(json.dumps(message))
                        self.messages_sent += 1
                        
                        # 等待响应
                        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        receive_time = time.time()
                        
                        data = json.loads(response)
                        latency = (receive_time - data['timestamp']) * 1000
                        self.latencies.append(latency)
                        self.messages_received += 1
                        
                    except Exception as e:
                        self.errors += 1
                        
        except Exception as e:
            print(f"Client {self.client_id}: Connection error - {e}")
    
    def get_stats(self) -> dict:
        if self.latencies:
            return {
                'client_id': self.client_id,
                'messages_sent': self.messages_sent,
                'messages_received': self.messages_received,
                'errors': self.errors,
                'avg_latency': statistics.mean(self.latencies),
                'p50_latency': statistics.median(self.latencies),
                'p95_latency': sorted(self.latencies)[int(len(self.latencies) * 0.95)],
                'p99_latency': sorted(self.latencies)[int(len(self.latencies) * 0.99)],
                'max_latency': max(self.latencies),
            }
        return {
            'client_id': self.client_id,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'errors': self.errors,
        }


async def stress_test(concurrent_clients: int = 10, messages_per_client: int = 50):
    """执行压力测试"""
    print(f"\n{'='*60}")
    print(f"WebSocket Stress Test")
    print(f"Concurrent clients: {concurrent_clients}")
    print(f"Messages per client: {messages_per_client}")
    print(f"Total messages: {concurrent_clients * messages_per_client}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    
    # 创建客户端
    clients = [
        StressTestClient(i, "ws://localhost:8087")
        for i in range(concurrent_clients)
    ]
    
    # 并行运行
    tasks = [c.run(messages_per_client) for c in clients]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    duration = time.time() - start_time
    
    # 汇总统计
    all_latencies = []
    total_sent = 0
    total_received = 0
    total_errors = 0
    
    for client in clients:
        stats = client.get_stats()
        total_sent += stats['messages_sent']
        total_received += stats['messages_received']
        total_errors += stats['errors']
        if 'avg_latency' in stats:
            all_latencies.extend(client.latencies)
    
    # 输出结果
    print(f"\n📊 Results:")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Messages sent: {total_sent}")
    print(f"  Messages received: {total_received}")
    print(f"  Success rate: {(total_received/total_sent)*100:.2f}%")
    print(f"  Errors: {total_errors}")
    print(f"  Throughput: {total_received/duration:.2f} msg/s")
    
    if all_latencies:
        print(f"\n⏱️ Latency Statistics:")
        print(f"  Average: {statistics.mean(all_latencies):.2f}ms")
        print(f"  Median: {statistics.median(all_latencies):.2f}ms")
        print(f"  P95: {sorted(all_latencies)[int(len(all_latencies)*0.95)]:.2f}ms")
        print(f"  P99: {sorted(all_latencies)[int(len(all_latencies)*0.99)]:.2f}ms")
        print(f"  Max: {max(all_latencies):.2f}ms")
    
    # 验收标准检查
    success_rate = (total_received / total_sent) * 100 if total_sent > 0 else 0
    avg_latency = statistics.mean(all_latencies) if all_latencies else float('inf')
    
    print(f"\n✅ Acceptance Criteria:")
    print(f"  Success rate > 99%: {'✅ PASS' if success_rate > 99 else '❌ FAIL'}")
    print(f"  Avg latency < 100ms: {'✅ PASS' if avg_latency < 100 else '❌ FAIL'}")
    
    return success_rate > 99 and avg_latency < 100


if __name__ == "__main__":
    # 运行压力测试
    result = asyncio.run(stress_test(concurrent_clients=10, messages_per_client=50))
    print(f"\n{'✅ PASSED' if result else '❌ FAILED'}")
```

#### 3.2.4 验收标准

| 指标 | 验收标准 | 测试方法 |
|------|----------|----------|
| 连接成功率 | > 99% | 100 次连接测试 |
| 消息延迟 (P95) | < 100ms | 压力测试 |
| 并发连接数 | >= 10 | 并发测试 |
| 断线重连 | 3 次内成功 | 重连测试 |
| 消息吞吐量 | > 100 msg/s | 压力测试 |

### 3.3 HTTP 通信验证

#### 3.3.1 验证目标

验证 HTTP 在以下场景的可行性：
1. REST API 调用性能
2. 文件上传/下载
3. 批量数据获取

#### 3.3.2 验证代码

```python
# test_http_api.py
"""HTTP API 性能测试"""

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict


class HTTPAPITester:
    """HTTP API 测试类"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.latencies = []
        self.errors = 0
        
    async def test_get(self, endpoint: str, session: aiohttp.ClientSession) -> float:
        """测试 GET 请求"""
        start = time.time()
        try:
            async with session.get(f"{self.base_url}{endpoint}") as resp:
                await resp.text()
                latency = (time.time() - start) * 1000
                self.latencies.append(latency)
                return latency
        except Exception as e:
            self.errors += 1
            return -1
    
    async def test_post(self, endpoint: str, data: dict, session: aiohttp.ClientSession) -> float:
        """测试 POST 请求"""
        start = time.time()
        try:
            async with session.post(f"{self.base_url}{endpoint}", json=data) as resp:
                await resp.text()
                latency = (time.time() - start) * 1000
                self.latencies.append(latency)
                return latency
        except Exception as e:
            self.errors += 1
            return -1
    
    async def run_concurrent_tests(self, endpoint: str, count: int = 100):
        """并发测试"""
        async with aiohttp.ClientSession() as session:
            tasks = [self.test_get(endpoint, session) for _ in range(count)]
            await asyncio.gather(*tasks)
    
    def get_stats(self) -> Dict:
        if not self.latencies:
            return {'error': 'No successful requests'}
        
        sorted_latencies = sorted(self.latencies)
        return {
            'total_requests': len(self.latencies) + self.errors,
            'successful': len(self.latencies),
            'errors': self.errors,
            'success_rate': len(self.latencies) / (len(self.latencies) + self.errors) * 100,
            'avg_latency_ms': statistics.mean(self.latencies),
            'min_latency_ms': min(self.latencies),
            'max_latency_ms': max(self.latencies),
            'p50_latency_ms': statistics.median(self.latencies),
            'p95_latency_ms': sorted_latencies[int(len(sorted_latencies) * 0.95)],
            'p99_latency_ms': sorted_latencies[int(len(sorted_latencies) * 0.99)],
        }


async def main():
    """主测试函数"""
    print("=" * 60)
    print("HTTP API Performance Test")
    print("=" * 60)
    
    # 测试配置
    tester = HTTPAPITester("http://localhost:8000")
    
    # 运行并发测试
    await tester.run_concurrent_tests("/api/health", count=100)
    
    # 输出结果
    stats = tester.get_stats()
    print(f"\n📊 Results:")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    # 验收检查
    print(f"\n✅ Acceptance Criteria:")
    success = stats.get('success_rate', 0) > 99
    latency = stats.get('p95_latency_ms', float('inf'))
    print(f"  Success rate > 99%: {'✅ PASS' if success else '❌ FAIL'}")
    print(f"  P95 latency < 200ms: {'✅ PASS' if latency < 200 else '❌ FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 3.4 验证结果记录模板

```markdown
## DCC 通信验证结果

### 测试环境
- 日期: YYYY-MM-DD
- 测试人员: [Name]
- DCC 版本: [Version]

### WebSocket 测试结果

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 基础连接 | ✅/❌ | |
| 并发连接 (10) | ✅/❌ | |
| 消息延迟 (P95) | XX ms | |
| 断线重连 | ✅/❌ | |
| 吞吐量 | XX msg/s | |

### HTTP 测试结果

| 测试项 | 结果 | 备注 |
|--------|------|------|
| GET 请求 | ✅/❌ | |
| POST 请求 | ✅/❌ | |
| P95 延迟 | XX ms | |
| 并发性能 | ✅/❌ | |

### 结论
[验证结论和建议]
```

---

## 4. OpenClaw Gateway 集成验证

### 4.1 验证目标

验证 ArtClaw Tool Manager 与 OpenClaw Gateway 的集成可行性：
1. Gateway 连接和认证
2. MCP Bridge 消息转发
3. 多 DCC 并发通信
4. 消息格式兼容性

### 4.2 架构回顾

基于 [gateway-forwarding-roadmap.md](../../../../docs/features/gateway-forwarding-roadmap.md) 的架构：

```
┌─────────────────────────────────────────────────────────────┐
│                    ArtClaw Tool Manager                      │
│                      (Web 前端 + FastAPI)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket/HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  OpenClaw Gateway                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              mcp-bridge plugin                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │  UE Bridge  │  │ Maya Bridge │  │ ComfyUI Br  │ │   │
│  │  │   :8080     │  │   :8081     │  │   :8087     │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  UE MCP     │ │  Maya MCP   │ │ ComfyUI MCP │
    │  Server     │ │  Server     │ │  Server     │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### 4.3 验证步骤

#### 4.3.1 Gateway 连接验证

```python
# test_gateway_connection.py
"""OpenClaw Gateway 连接验证"""

import asyncio
import websockets
import json
from typing import Optional, Dict, Any


class GatewayClient:
    """Gateway 客户端测试类"""
    
    def __init__(self, gateway_url: str = "ws://localhost:3000"):
        self.gateway_url = gateway_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.session_key: Optional[str] = None
        self.message_count = 0
        
    async def connect(self) -> bool:
        """连接到 Gateway"""
        try:
            self.websocket = await websockets.connect(self.gateway_url)
            print(f"✅ Connected to Gateway: {self.gateway_url}")
            return True
        except Exception as e:
            print(f"❌ Gateway connection failed: {e}")
            return False
    
    async def authenticate(self, token: str) -> bool:
        """认证"""
        auth_msg = {
            'type': 'auth',
            'token': token
        }
        await self.websocket.send(json.dumps(auth_msg))
        
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data.get('status') == 'success':
            self.session_key = data.get('session_key')
            print(f"✅ Authenticated, session: {self.session_key}")
            return True
        else:
            print(f"❌ Authentication failed: {data}")
            return False
    
    async def send_to_dcc(self, dcc_type: str, message: Dict[str, Any]):
        """发送消息到指定 DCC"""
        msg = {
            'type': 'mcp_request',
            'target': dcc_type,
            'session_key': self.session_key,
            'payload': message
        }
        await self.websocket.send(json.dumps(msg))
        self.message_count += 1
        
    async def receive_response(self, timeout: float = 30.0) -> Optional[Dict]:
        """接收响应"""
        try:
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )
            return json.loads(response)
        except asyncio.TimeoutError:
            print("❌ Response timeout")
            return None
        except Exception as e:
            print(f"❌ Receive error: {e}")
            return None
    
    async def test_dcc_connection(self, dcc_type: str) -> bool:
        """测试 DCC 连接"""
        print(f"\n📡 Testing {dcc_type} connection...")
        
        # 发送 ping
        ping_msg = {
            'tool': 'get_context',
            'params': {}
        }
        await self.send_to_dcc(dcc_type, ping_msg)
        
        # 等待响应
        response = await self.receive_response(timeout=5.0)
        
        if response and response.get('status') == 'success':
            print(f"✅ {dcc_type} connection OK")
            return True
        else:
            print(f"❌ {dcc_type} connection failed: {response}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            print("✅ Disconnected from Gateway")


async def test_gateway_integration():
    """测试 Gateway 集成"""
    print("=" * 60)
    print("OpenClaw Gateway Integration Test")
    print("=" * 60)
    
    client = GatewayClient("ws://localhost:3000")
    
    # 1. 连接 Gateway
    if not await client.connect():
        return False
    
    # 2. 认证（使用测试 token）
    if not await client.authenticate("test_token"):
        return False
    
    # 3. 测试各 DCC 连接
    dcc_types = ["ue5", "maya2024", "comfyui"]
    results = {}
    
    for dcc in dcc_types:
        results[dcc] = await client.test_dcc_connection(dcc)
        await asyncio.sleep(0.5)  # 间隔避免拥堵
    
    # 4. 断开
    await client.disconnect()
    
    # 5. 输出结果
    print(f"\n📊 Results:")
    for dcc, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {dcc}")
    
    all_passed = all(results.values())
    print(f"\n{'✅ PASSED' if all_passed else '❌ FAILED'}")
    
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(test_gateway_integration())
```

#### 4.3.2 MCP Bridge 消息转发验证

```python
# test_mcp_bridge.py
"""MCP Bridge 消息转发验证"""

import asyncio
import websockets
import json
import time
from typing import Dict, List


class MCPBridgeTester:
    """MCP Bridge 测试类"""
    
    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.websocket = None
        self.responses: List[Dict] = []
        
    async def connect(self):
        self.websocket = await websockets.connect(self.gateway_url)
        
    async def send_tool_call(self, dcc_type: str, tool: str, params: dict) -> Dict:
        """发送工具调用"""
        message = {
            'type': 'tool_call',
            'target': dcc_type,
            'tool': tool,
            'params': params,
            'timestamp': time.time()
        }
        
        await self.websocket.send(json.dumps(message))
        
        # 等待响应
        response = await self.websocket.recv()
        return json.loads(response)
    
    async def test_tool_execution(self, dcc_type: str) -> Dict:
        """测试工具执行"""
        print(f"\n🔧 Testing tool execution on {dcc_type}")
        
        # 测试 get_context 工具
        start = time.time()
        response = await self.send_tool_call(
            dcc_type=dcc_type,
            tool='get_context',
            params={}
        )
        latency = (time.time() - start) * 1000
        
        success = response.get('status') == 'success'
        print(f"  Status: {'✅' if success else '❌'}")
        print(f"  Latency: {latency:.2f}ms")
        
        return {
            'dcc': dcc_type,
            'success': success,
            'latency_ms': latency,
            'response': response
        }
    
    async def test_concurrent_calls(self, dcc_type: str, count: int = 10) -> Dict:
        """测试并发调用"""
        print(f"\n⚡ Testing {count} concurrent calls on {dcc_type}")
        
        start = time.time()
        tasks = [
            self.send_tool_call(dcc_type, 'get_context', {})
            for _ in range(count)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.time() - start
        
        successes = sum(1 for r in responses if isinstance(r, dict) and r.get('status') == 'success')
        
        print(f"  Success: {successes}/{count}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Throughput: {count/duration:.2f} calls/s")
        
        return {
            'dcc': dcc_type,
            'total': count,
            'success': successes,
            'duration_ms': duration * 1000,
            'throughput': count / duration
        }
    
    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()


async def main():
    """主测试函数"""
    print("=" * 60)
    print("MCP Bridge Message Forwarding Test")
    print("=" * 60)
    
    tester = MCPBridgeTester("ws://localhost:3000")
    await tester.connect()
    
    # 测试各 DCC 的工具执行
    dcc_types = ["ue5", "maya2024", "comfyui"]
    results = []
    
    for dcc in dcc_types:
        # 单工具测试
        result = await tester.test_tool_execution(dcc)
        results.append(result)
        
        # 并发测试
        if result['success']:
            concurrent_result = await tester.test_concurrent_calls(dcc, count=10)
            results.append(concurrent_result)
    
    await tester.disconnect()
    
    # 输出汇总
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    
    for r in results:
        print(f"  {r}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.4 验收标准

| 验证项 | 验收标准 | 优先级 |
|--------|----------|--------|
| Gateway 连接 | 连接成功率 > 99% | P0 |
| 认证流程 | 认证延迟 < 500ms | P0 |
| 消息转发 | 成功率 > 99.9% | P0 |
| 转发延迟 (P95) | < 200ms | P0 |
| 并发处理 | 支持 10+ 并发 | P1 |
| 多 DCC 支持 | 同时连接 >= 3 个 DCC | P0 |

---

## 5. 对话面板技术方案验证

### 5.1 技术选型

基于架构设计，对话面板需要以下技术能力：

| 功能 | 技术方案 | 选型理由 |
|------|----------|----------|
| 前端框架 | React + TypeScript | 生态成熟，类型安全 |
| 状态管理 | Zustand | 轻量，TypeScript 友好 |
| UI 组件 | Tailwind CSS + Headless UI | 定制化程度高 |
| 实时通信 | WebSocket | 双向实时通信 |
| 消息渲染 | 虚拟列表 (react-window) | 大数据量性能优化 |
| 表单渲染 | React Hook Form | 性能优秀，验证灵活 |

### 5.2 验证 POC

#### 5.2.1 消息流性能测试

```typescript
// MessageStreamPerformance.tsx
// 消息流渲染性能测试组件

import React, { useState, useCallback, useMemo } from 'react';
import { FixedSizeList as List } from 'react-window';
import AutoSizer from 'react-virtualized-auto-sizer';

interface Message {
  id: string;
  type: 'user' | 'assistant' | 'tool';
  content: string;
  timestamp: number;
}

// 生成测试数据
const generateMessages = (count: number): Message[] => {
  return Array.from({ length: count }, (_, i) => ({
    id: `msg-${i}`,
    type: i % 3 === 0 ? 'user' : i % 3 === 1 ? 'assistant' : 'tool',
    content: `Message content ${i} `.repeat(20),
    timestamp: Date.now() - (count - i) * 1000,
  }));
};

// 消息项组件
const MessageItem = React.memo(({ 
  index, 
  style, 
  data 
}: {
  index: number;
  style: React.CSSProperties;
  data: Message[];
}) => {
  const message = data[index];
  
  return (
    <div style={style} className="p-2">
      <div className={`rounded-lg p-3 ${
        message.type === 'user' 
          ? 'bg-blue-100 ml-auto' 
          : message.type === 'assistant'
          ? 'bg-gray-100'
          : 'bg-green-100'
      } max-w-[80%]`}>
        <div className="text-xs text-gray-500 mb-1">
          {message.type} • {new Date(message.timestamp).toLocaleTimeString()}
        </div>
        <div className="text-sm">{message.content}</div>
      </div>
    </div>
  );
});

// 性能测试组件
export const MessageStreamPerformance: React.FC = () => {
  const [messageCount, setMessageCount] = useState(100);
  const [messages, setMessages] = useState<Message[]>(() => generateMessages(100));
  const [renderTime, setRenderTime] = useState(0);
  const [scrollPerformance, setScrollPerformance] = useState(0);

  // 测试大量消息渲染
  const testLargeDataset = useCallback((count: number) => {
    const start = performance.now();
    const newMessages = generateMessages(count);
    setMessages(newMessages);
    setMessageCount(count);
    
    // 使用 requestAnimationFrame 测量实际渲染时间
    requestAnimationFrame(() => {
      const end = performance.now();
      setRenderTime(end - start);
    });
  }, []);

  // 测试滚动性能
  const testScrollPerformance = useCallback(() => {
    const list = document.querySelector('[data-testid="message-list"]') as HTMLElement;
    if (!list) return;

    const scrollStart = performance.now();
    let frames = 0;
    let startTime = scrollStart;

    const animate = () => {
      frames++;
      const currentTime = performance.now();
      
      if (currentTime - startTime < 1000) {
        // 持续滚动 1 秒
        list.scrollTop = (list.scrollTop + 100) % list.scrollHeight;
        requestAnimationFrame(animate);
      } else {
        const fps = frames / ((currentTime - startTime) / 1000);
        setScrollPerformance(fps);
      }
    };

    requestAnimationFrame(animate);
  }, []);

  // 计算平均消息高度
  const getItemSize = useCallback((index: number) => {
    const message = messages[index];
    // 根据内容长度估算高度
    const baseHeight = 60;
    const contentHeight = Math.ceil(message.content.length / 50) * 20;
    return Math.min(baseHeight + contentHeight, 200);
  }, [messages]);

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">Message Stream Performance Test</h2>
      
      {/* 控制面板 */}
      <div className="mb-4 space-x-2">
        {[100, 500, 1000, 5000].map(count => (
          <button
            key={count}
            onClick={() => testLargeDataset(count)}
            className="px-4 py-2 bg-blue-500 text-white rounded"
          >
            Load {count} Messages
          </button>
        ))}
        <button
          onClick={testScrollPerformance}
          className="px-4 py-2 bg-green-500 text-white rounded"
        >
          Test Scroll Performance
        </button>
      </div>

      {/* 性能指标 */}
      <div className="mb-4 grid grid-cols-3 gap-4">
        <div className="bg-gray-100 p-3 rounded">
          <div className="text-sm text-gray-600">Message Count</div>
          <div className="text-2xl font-bold">{messageCount}</div>
        </div>
        <div className="bg-gray-100 p-3 rounded">
          <div className="text-sm text-gray-600">Render Time</div>
          <div className={`text-2xl font-bold ${renderTime < 100 ? 'text-green-600' : 'text-red-600'}`}>
            {renderTime.toFixed(2)}ms
          </div>
        </div>
        <div className="bg-gray-100 p-3 rounded">
          <div className="text-sm text-gray-600">Scroll FPS</div>
          <div className={`text-2xl font-bold ${scrollPerformance >= 30 ? 'text-green-600' : 'text-red-600'}`}>
            {scrollPerformance > 0 ? `${scrollPerformance.toFixed(1)} FPS` : '-'}
          </div>
        </div>
      </div>

      {/* 验收标准 */}
      <div className="mb-4 p-3 bg-blue-50 rounded">
        <h3 className="font-semibold mb-2">Acceptance Criteria:</h3>
        <ul className="text-sm space-y-1">
          <li className={renderTime < 100 ? 'text-green-600' : 'text-red-600'}>
            {renderTime < 100 ? '✅' : '❌'} Initial render &lt; 100ms
          </li>
          <li className={scrollPerformance >= 30 ? 'text-green-600' : 'text-red-600'}>
            {scrollPerformance >= 30 ? '✅' : '❌'} Scroll FPS &gt;= 30
          </li>
        </ul>
      </div>

      {/* 消息列表 */}
      <div className="border rounded h-[500px]" data-testid="message-list">
        <AutoSizer>
          {({ height, width }) => (
            <List
              height={height}
              width={width}
              itemCount={messages.length}
              itemSize={100}
              itemData={messages}
            >
              {MessageItem}
            </List>
          )}
        </AutoSizer>
      </div>
    </div>
  );
};

export default MessageStreamPerformance;
```

#### 5.2.2 动态表单渲染测试

```typescript
// DynamicFormPerformance.tsx
// 右侧面板动态表单性能测试

import React, { useState, useCallback } from 'react';
import { useForm, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

// 参数定义类型
interface Parameter {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean' | 'enum' | 'image';
  required: boolean;
  default?: any;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  description?: string;
}

// 生成测试参数
const generateParameters = (count: number): Parameter[] => {
  const types: Parameter['type'][] = ['string', 'number', 'boolean', 'enum'];
  return Array.from({ length: count }, (_, i) => ({
    id: `param-${i}`,
    name: `Parameter ${i}`,
    type: types[i % types.length],
    required: i % 3 === 0,
    default: types[i % types.length] === 'number' ? 50 : 
             types[i % types.length] === 'boolean' ? false : 
             types[i % types.length] === 'enum' ? 'option1' : 'default value',
    min: types[i % types.length] === 'number' ? 0 : undefined,
    max: types[i % types.length] === 'number' ? 100 : undefined,
    step: types[i % types.length] === 'number' ? 1 : undefined,
    options: types[i % types.length] === 'enum' 
      ? ['option1', 'option2', 'option3', 'option4'] 
      : undefined,
    description: `Description for parameter ${i}`,
  }));
};

// 动态表单字段组件
const DynamicField: React.FC<{ param: Parameter }> = ({ param }) => {
  const { register, formState: { errors } } = useForm();

  const renderInput = () => {
    switch (param.type) {
      case 'string':
        return (
          <input
            {...register(param.id, { required: param.required })}
            type="text"
            defaultValue={param.default}
            className="w-full px-3 py-2 border rounded"
            placeholder={param.description}
          />
        );
      
      case 'number':
        return (
          <div className="flex items-center space-x-2">
            <input
              {...register(param.id, { 
                required: param.required,
                min: param.min,
                max: param.max,
              })}
              type="range"
              min={param.min}
              max={param.max}
              step={param.step}
              defaultValue={param.default}
              className="flex-1"
            />
            <span className="w-16 text-right">{param.default}</span>
          </div>
        );
      
      case 'boolean':
        return (
          <input
            {...register(param.id)}
            type="checkbox"
            defaultChecked={param.default}
            className="w-5 h-5"
          />
        );
      
      case 'enum':
        return (
          <select
            {...register(param.id, { required: param.required })}
            defaultValue={param.default}
            className="w-full px-3 py-2 border rounded"
          >
            {param.options?.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium mb-1">
        {param.name}
        {param.required && <span className="text-red-500">*</span>}
      </label>
      {renderInput()}
      {param.description && (
        <p className="text-xs text-gray-500 mt-1">{param.description}</p>
      )}
      {errors[param.id] && (
        <p className="text-xs text-red-500 mt-1">This field is required</p>
      )}
    </div>
  );
};

// 性能测试组件
export const DynamicFormPerformance: React.FC = () => {
  const [paramCount, setParamCount] = useState(10);
  const [parameters, setParameters] = useState<Parameter[]>(() => generateParameters(10));
  const [renderTime, setRenderTime] = useState(0);
  const [validationTime, setValidationTime] = useState(0);

  const methods = useForm({
    mode: 'onChange',
  });

  // 测试表单渲染
  const testFormRender = useCallback((count: number) => {
    const start = performance.now();
    const newParams = generateParameters(count);
    setParameters(newParams);
    setParamCount(count);
    
    requestAnimationFrame(() => {
      const end = performance.now();
      setRenderTime(end - start);
    });
  }, []);

  // 测试表单验证
  const testValidation = useCallback(async () => {
    const start = performance.now();
    await methods.trigger();
    const end = performance.now();
    setValidationTime(end - start);
  }, [methods]);

  const onSubmit = (data: any) => {
    console.log('Form submitted:', data);
  };

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">Dynamic Form Performance Test</h2>
      
      {/* 控制面板 */}
      <div className="mb-4 space-x-2">
        {[10, 20, 50, 100].map(count => (
          <button
            key={count}
            onClick={() => testFormRender(count)}
            className="px-4 py-2 bg-blue-500 text-white rounded"
          >
            Load {count} Fields
          </button>
        ))}
        <button
          onClick={testValidation}
          className="px-4 py-2 bg-green-500 text-white rounded"
        >
          Test Validation
        </button>
      </div>

      {/* 性能指标 */}
      <div className="mb-4 grid grid-cols-3 gap-4">
        <div className="bg-gray-100 p-3 rounded">
          <div className="text-sm text-gray-600">Field Count</div>
          <div className="text-2xl font-bold">{paramCount}</div>
        </div>
        <div className="bg-gray-100 p-3 rounded">
          <div className="text-sm text-gray-600">Render Time</div>
          <div className={`text-2xl font-bold ${renderTime < 100 ? 'text-green-600' : 'text-red-600'}`}>
            {renderTime.toFixed(2)}ms
          </div>
        </div>
        <div className="bg-gray-100 p-3 rounded">
          <div className="text-sm text-gray-600">Validation Time</div>
          <div className={`text-2xl font-bold ${validationTime < 50 ? 'text-green-600' : 'text-red-600'}`}>
            {validationTime > 0 ? `${validationTime.toFixed(2)}ms` : '-'}
          </div>
        </div>
      </div>

      {/* 验收标准 */}
      <div className="mb-4 p-3 bg-blue-50 rounded">
        <h3 className="font-semibold mb-2">Acceptance Criteria:</h3>
        <ul className="text-sm space-y-1">
          <li className={renderTime < 100 ? 'text-green-600' : 'text-red-600'}>
            {renderTime < 100 ? '✅' : '❌'} Form render &lt; 100ms (50 fields)
          </li>
          <li className={validationTime < 50 ? 'text-green-600' : 'text-red-600'}>
            {validationTime < 50 ? '✅' : '❌'} Validation &lt; 50ms
          </li>
        </ul>
      </div>

      {/* 动态表单 */}
      <FormProvider {...methods}>
        <form onSubmit={methods.handleSubmit(onSubmit)} className="border rounded p-4">
          <h3 className="font-semibold mb-4">Workflow Parameters</h3>
          
          {parameters.map(param => (
            <DynamicField key={param.id} param={param} />
          ))}
          
          <div className="flex space-x-2 mt-4">
            <button
              type="submit"
              className="px-4 py-2 bg-blue-500 text-white rounded"
            >
              Execute
            </button>
            <button
              type="button"
              onClick={() => methods.reset()}
              className="px-4 py-2 bg-gray-300 rounded"
            >
              Reset
            </button>
          </div>
        </form>
      </FormProvider>
    </div>
  );
};

export default DynamicFormPerformance;
```

### 5.3 验收标准

| 验证项 | 验收标准 | 优先级 |
|--------|----------|--------|
| 消息渲染 | 1000 条消息渲染 < 100ms | P0 |
| 滚动性能 | 滚动 FPS >= 30 | P0 |
| 表单渲染 | 50 个字段渲染 < 100ms | P0 |
| 表单验证 | 验证响应 < 50ms | P1 |
| 内存占用 | 1000 条消息 < 50MB | P1 |

---

## 6. 数据存储方案选择

### 6.1 方案对比

#### 6.1.1 JSON 文件方案

**适用场景**:
- 用户配置（`~/.artclaw/config.json`）
- Skill 元数据缓存
- 工具定义文件

**优点**:
- 人类可读，易于调试
- 版本控制友好
- 无额外依赖
- 跨平台兼容

**缺点**:
- 大文件读写性能差
- 无查询能力
- 并发写入需额外处理
- 无事务支持

#### 6.1.2 SQLite 方案

**适用场景**:
- 消息历史记录
- 使用统计数据
- 搜索索引

**优点**:
- 结构化查询
- 事务支持
- 并发安全
- 性能优秀

**缺点**:
- 增加依赖
- 二进制文件，不便版本控制
- 需要迁移管理

### 6.2 推荐方案：混合存储

| 数据类型 | 存储方案 | 理由 |
|----------|----------|------|
| 用户配置 | JSON | 人类可读，手动编辑 |
| Skill/Workflow 元数据 | JSON | 静态数据，缓存为主 |
| 消息历史 | SQLite | 需要查询和分页 |
| 使用统计 | SQLite | 结构化数据，聚合查询 |
| 工具定义 | JSON | 版本控制，手动编辑 |

### 6.3 验证 POC

#### 6.3.1 JSON 读写性能测试

```python
# test_json_storage.py
"""JSON 存储性能测试"""

import json
import time
import os
from pathlib import Path
from typing import Dict, Any


class JSONStorageTester:
    """JSON 存储测试类"""
    
    def __init__(self, test_dir: str = "./test_data"):
        self.test_dir = Path(test_dir)
        self.test_dir.mkdir(exist_ok=True)
        
    def generate_config(self, size: str = "small") -> Dict[str, Any]:
        """生成测试配置"""
        sizes = {
            "small": 10,
            "medium": 100,
            "large": 1000,
        }
        count = sizes.get(size, 10)
        
        return {
            "version": "1.0.0",
            "settings": {
                "theme": "dark",
                "language": "zh-CN",
            },
            "skills": [
                {
                    "id": f"skill-{i}",
                    "name": f"Skill {i}",
                    "enabled": i % 2 == 0,
                    "priority": i,
                    "config": {"param1": f"value{i}", "param2": i * 10}
                }
                for i in range(count)
            ],
            "workflows": [
                {
                    "id": f"workflow-{i}",
                    "name": f"Workflow {i}",
                    "favorited": i % 3 == 0,
                    "lastUsed": time.time() - i * 3600,
                }
                for i in range(count // 2)
            ],
        }
    
    def test_write(self, config: Dict, filename: str) -> float:
        """测试写入性能"""
        filepath = self.test_dir / filename
        
        start = time.time()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        duration = time.time() - start
        
        file_size = filepath.stat().st_size
        print(f"  Write: {duration*1000:.2f}ms, Size: {file_size/1024:.2f}KB")
        
        return duration
    
    def test_read(self, filename: str) -> float:
        """测试读取性能"""
        filepath = self.test_dir / filename
        
        start = time.time()
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        duration = time.time() - start
        
        print(f"  Read: {duration*1000:.2f}ms")
        return duration
    
    def test_incremental_update(self, filename: str) -> float:
        """测试增量更新性能"""
        filepath = self.test_dir / filename
        
        # 读取
        start = time.time()
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 修改
        data['skills'][0]['enabled'] = not data['skills'][0]['enabled']
        
        # 写回
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        duration = time.time() - start
        print(f"  Incremental update: {duration*1000:.2f}ms")
        return duration
    
    def run_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("JSON Storage Performance Test")
        print("=" * 60)
        
        results = {}
        
        for size in ["small", "medium", "large"]:
            print(f"\n📦 Testing {size} dataset...")
            config = self.generate_config(size)
            filename = f"config_{size}.json"
            
            write_time = self.test_write(config, filename)
            read_time = self.test_read(filename)
            update_time = self.test_incremental_update(filename)
            
            results[size] = {
                "write_ms": write_time * 1000,
                "read_ms": read_time * 1000,
                "update_ms": update_time * 1000,
            }
        
        # 输出汇总
        print(f"\n{'='*60}")
        print("Summary")
        print(f"{'='*60}")
        for size, metrics in results.items():
            print(f"\n{size.upper()}:")
            for metric, value in metrics.items():
                status = "✅" if value < 100 else "⚠️" if value < 500 else "❌"
                print(f"  {status} {metric}: {value:.2f}ms")
        
        # 验收标准
        print(f"\n{'='*60}")
        print("Acceptance Criteria:")
        print(f"{'='*60}")
        medium_results = results.get("medium", {})
        print(f"  Write < 100ms: {'✅ PASS' if medium_results.get('write_ms', 0) < 100 else '❌ FAIL'}")
        print(f"  Read < 50ms: {'✅ PASS' if medium_results.get('read_ms', 0) < 50 else '❌ FAIL'}")
        print(f"  Update < 200ms: {'✅ PASS' if medium_results.get('update_ms', 0) < 200 else '❌ FAIL'}")
        
        return results


if __name__ == "__main__":
    tester = JSONStorageTester()
    tester.run_tests()
```

#### 6.3.2 SQLite 性能测试

```python
# test_sqlite_storage.py
"""SQLite 存储性能测试"""

import sqlite3
import time
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict


class SQLiteStorageTester:
    """SQLite 存储测试类"""
    
    def __init__(self, db_path: str = "./test_data/messages.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.conn = None
        
    def init_database(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # 创建消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                type TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                timestamp REAL NOT NULL,
                metadata TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_session_time 
            ON messages(session_id, timestamp)
        ''')
        
        self.conn.commit()
        
    def generate_messages(self, count: int, session_id: str = "test-session") -> List[Dict]:
        """生成测试消息"""
        messages = []
        base_time = datetime.now()
        
        for i in range(count):
            msg = {
                'session_id': session_id,
                'type': random.choice(['text', 'tool_call', 'image']),
                'role': random.choice(['user', 'assistant']),
                'content': f"Message content {i} " * 20,
                'timestamp': (base_time - timedelta(minutes=i)).timestamp(),
                'metadata': json.dumps({'param1': i, 'param2': f'value{i}'})
            }
            messages.append(msg)
        
        return messages
    
    def test_batch_insert(self, messages: List[Dict]) -> float:
        """测试批量插入性能"""
        cursor = self.conn.cursor()
        
        start = time.time()
        cursor.executemany('''
            INSERT INTO messages (session_id, type, role, content, timestamp, metadata)
            VALUES (:session_id, :type, :role, :content, :timestamp, :metadata)
        ''', messages)
        self.conn.commit()
        duration = time.time() - start
        
        print(f"  Batch insert {len(messages)} records: {duration*1000:.2f}ms "
              f"({len(messages)/duration:.0f} records/s)")
        return duration
    
    def test_query_pagination(self, session_id: str, page_size: int = 50) -> float:
        """测试分页查询性能"""
        cursor = self.conn.cursor()
        
        start = time.time()
        cursor.execute('''
            SELECT * FROM messages 
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET 0
        ''', (session_id, page_size))
        results = cursor.fetchall()
        duration = time.time() - start
        
        print(f"  Query {len(results)} records: {duration*1000:.2f}ms")
        return duration
    
    def test_search(self, keyword: str) -> float:
        """测试搜索性能"""
        cursor = self.conn.cursor()
        
        start = time.time()
        cursor.execute('''
            SELECT * FROM messages 
            WHERE content LIKE ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (f'%{keyword}%',))
        results = cursor.fetchall()
        duration = time.time() - start
        
        print(f"  Search '{keyword}': {len(results)} results in {duration*1000:.2f}ms")
        return duration
    
    def test_aggregation(self, session_id: str) -> float:
        """测试聚合查询性能"""
        cursor = self.conn.cursor()
        
        start = time.time()
        cursor.execute('''
            SELECT 
                type,
                role,
                COUNT(*) as count,
                MIN(timestamp) as first_msg,
                MAX(timestamp) as last_msg
            FROM messages 
            WHERE session_id = ?
            GROUP BY type, role
        ''', (session_id,))
        results = cursor.fetchall()
        duration = time.time() - start
        
        print(f"  Aggregation query: {len(results)} groups in {duration*1000:.2f}ms")
        return duration
    
    def run_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("SQLite Storage Performance Test")
        print("=" * 60)
        
        self.init_database()
        
        results = {}
        
        # 测试不同数据量
        for count in [100, 1000, 10000]:
            print(f"\n📦 Testing with {count} messages...")
            
            # 生成数据
            messages = self.generate_messages(count, f"session-{count}")
            
            # 批量插入
            insert_time = self.test_batch_insert(messages)
            
            # 分页查询
            query_time = self.test_query_pagination(f"session-{count}", page_size=50)
            
            # 搜索
            search_time = self.test_search("content 50")
            
            # 聚合
            agg_time = self.test_aggregation(f"session-{count}")
            
            results[count] = {
                'insert_ms': insert_time * 1000,
                'query_ms': query_time * 1000,
                'search_ms': search_time * 1000,
                'aggregation_ms': agg_time * 1000,
            }
        
        # 输出汇总
        print(f"\n{'='*60}")
        print("Summary")
        print(f"{'='*60}")
        for count, metrics in results.items():
            print(f"\n{count} messages:")
            for metric, value in metrics.items():
                print(f"  {metric}: {value:.2f}ms")
        
        # 验收标准（基于 1000 条数据）
        print(f"\n{'='*60}")
        print("Acceptance Criteria (1000 messages):")
        print(f"{'='*60}")
        m = results.get(1000, {})
        print(f"  Insert < 500ms: {'✅ PASS' if m.get('insert_ms', 0) < 500 else '❌ FAIL'}")
        print(f"  Query < 50ms: {'✅ PASS' if m.get('query_ms', 0) < 50 else '❌ FAIL'}")
        print(f"  Search < 100ms: {'✅ PASS' if m.get('search_ms', 0) < 100 else '❌ FAIL'}")
        
        self.conn.close()
        return results


if __name__ == "__main__":
    import json
    tester = SQLiteStorageTester()
    tester.run_tests()
```

### 6.4 数据模型设计验证

```typescript
// storage-schema.ts
// 数据存储 Schema 定义

// ==================== JSON 存储 Schema ====================

// ~/.artclaw/config.json
export interface UserConfig {
  version: string;
  settings: {
    theme: 'light' | 'dark' | 'system';
    language: 'zh-CN' | 'en-US';
    autoUpdate: boolean;
  };
  dccSettings: {
    [dccType: string]: {
      enabled: boolean;
      port: number;
      autoConnect: boolean;
    };
  };
}

// ~/.artclaw/skills/config.json
export interface SkillsConfig {
  pinned: string[];        // 钉选的 Skill ID 列表
  disabled: string[];      // 禁用的 Skill ID 列表
  favorites: string[];     // 收藏的 Skill ID 列表
  recent: {                // 最近使用
    skillId: string;
    timestamp: number;
  }[];
}

// ~/.artclaw/workflows/config.json
export interface WorkflowsConfig {
  favorites: string[];
  recent: {
    workflowId: string;
    timestamp: number;
  }[];
}

// ~/.artclaw/tools/config.json
export interface ToolsConfig {
  favorites: string[];
  recent: {
    toolId: string;
    timestamp: number;
  }[];
}

// ==================== SQLite Schema ====================

// 消息表
export interface MessageRecord {
  id: number;
  sessionId: string;
  type: 'text' | 'tool_call' | 'tool_result' | 'image' | 'file';
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  metadata?: string;  // JSON string
}

// 会话表
export interface SessionRecord {
  id: string;
  title: string;
  dccType: string;
  agentPlatform: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

// 使用统计表
export interface UsageStatsRecord {
  id: number;
  date: string;  // YYYY-MM-DD
  dccType: string;
  toolName: string;
  callCount: number;
  avgLatency: number;
  successCount: number;
  errorCount: number;
}
```

### 6.5 验收标准

| 验证项 | JSON 标准 | SQLite 标准 | 优先级 |
|--------|-----------|-------------|--------|
| 写入性能 | < 100ms (medium) | < 500ms (1000 rows) | P0 |
| 读取性能 | < 50ms | < 50ms (pagination) | P0 |
| 搜索性能 | N/A | < 100ms | P1 |
| 并发安全 | 文件锁 | 原生支持 | P1 |

---

## 7. 风险评估与应对方案

### 7.1 技术风险矩阵

| 风险项 | 可能性 | 影响 | 风险等级 | 应对方案 |
|--------|--------|------|----------|----------|
| WebSocket 连接不稳定 | 中 | 高 | 🔴 高 | 实现断线重连 + HTTP 降级 |
| Gateway 转发延迟高 | 低 | 高 | 🟡 中 | 本地缓存 + 异步处理 |
| 消息流渲染卡顿 | 中 | 中 | 🟡 中 | 虚拟列表 + 懒加载 |
| 数据存储性能不足 | 低 | 中 | 🟢 低 | 混合存储 + 缓存策略 |
| DCC 版本兼容性 | 中 | 中 | 🟡 中 | 版本检测 + 适配层 |
| 并发连接数限制 | 低 | 低 | 🟢 低 | 连接池管理 |

### 7.2 详细应对方案

#### 7.2.1 WebSocket 连接不稳定

**风险描述**: DCC 软件可能崩溃或网络波动导致 WebSocket 连接中断

**应对方案**:
```typescript
// websocket-manager.ts
class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // 初始延迟 1s
  private messageQueue: any[] = [];
  
  connect(url: string) {
    this.ws = new WebSocket(url);
    
    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.flushMessageQueue();
    };
    
    this.ws.onclose = () => {
      this.handleReconnect(url);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.fallbackToHTTP();
    };
  }
  
  private handleReconnect(url: string) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      this.fallbackToHTTP();
      return;
    }
    
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts),
      30000 // 最大 30s
    );
    
    setTimeout(() => {
      this.reconnectAttempts++;
      this.connect(url);
    }, delay);
  }
  
  private fallbackToHTTP() {
    // 切换到 HTTP 轮询模式
    console.log('Falling back to HTTP polling');
    // ...
  }
  
  private flushMessageQueue() {
    while (this.messageQueue.length > 0) {
      const msg = this.messageQueue.shift();
      this.send(msg);
    }
  }
  
  send(message: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      this.messageQueue.push(message);
    }
  }
}
```

#### 7.2.2 Gateway 转发延迟高

**风险描述**: OpenClaw Gateway 转发消息可能出现延迟

**应对方案**:
1. **本地缓存**: 缓存常用 Skill 和工具定义
2. **异步处理**: 非关键操作异步执行
3. **超时机制**: 设置合理的超时时间
4. **降级策略**: Gateway 不可用时使用本地模式

```typescript
// gateway-client.ts
class GatewayClient {
  private cache = new Map<string, any>();
  private cacheTTL = 5 * 60 * 1000; // 5 分钟
  
  async requestWithCache<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: { ttl?: number; fallback?: T } = {}
  ): Promise<T> {
    // 检查缓存
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.timestamp < (options.ttl || this.cacheTTL)) {
      return cached.data;
    }
    
    try {
      // 带超时的请求
      const data = await Promise.race([
        fetcher(),
        new Promise<never>((_, reject) => 
          setTimeout(() => reject(new Error('Timeout')), 10000)
        )
      ]);
      
      // 更新缓存
      this.cache.set(key, { data, timestamp: Date.now() });
      return data;
      
    } catch (error) {
      // 使用缓存或 fallback
      if (cached) return cached.data;
      if (options.fallback) return options.fallback;
      throw error;
    }
  }
}
```

#### 7.2.3 消息流渲染卡顿

**风险描述**: 大量消息时 UI 可能出现卡顿

**应对方案**:
1. **虚拟列表**: 只渲染可见区域的消息
2. **消息合并**: 连续的消息合并显示
3. **懒加载**: 历史消息按需加载
4. **Web Worker**: 复杂处理放到后台线程

### 7.3 应急预案

| 场景 | 应急措施 | 恢复流程 |
|------|----------|----------|
| Gateway 完全不可用 | 切换到本地模式，使用缓存数据 | 检测 Gateway 恢复后自动重连 |
| WebSocket 全部失败 | 降级到 HTTP 轮询 | WebSocket 恢复后自动升级 |
| 前端崩溃 | 自动保存草稿，刷新恢复 | 重新加载后恢复会话状态 |
| 数据损坏 | 从备份恢复 | 定期自动备份配置 |

---

## 8. 预研结果文档化要求

### 8.1 文档输出清单

| 文档 | 内容 | 格式 | 位置 |
|------|------|------|------|
| 技术验证报告 | 各项技术验证结果 | Markdown | 本文档 |
| POC 代码 | 验证代码和脚本 | Python/TS | `tests/poc/` |
| 性能基准 | 性能测试数据 | JSON/Markdown | `tests/benchmarks/` |
| 技术选型决策 | 最终技术选型记录 | Markdown | `docs/decisions/` |
| 风险评估报告 | 风险分析和应对方案 | Markdown | 本文档第 7 章 |

### 8.2 验证结果记录模板

```markdown
## 验证结果记录

### 验证项: [名称]
- **验证日期**: YYYY-MM-DD
- **验证人员**: [Name]
- **环境**: [OS/版本/依赖]

### 测试数据
| 指标 | 目标值 | 实际值 | 结果 |
|------|--------|--------|------|
| 指标1 | XX | XX | ✅/❌ |

### 结论
[验证结论]

### 建议
[后续建议]
```

### 8.3 技术决策记录 (ADR)

```markdown
# ADR-001: DCC 通信协议选择

## 状态
- 提议 / 已接受 / 已弃用 / 已取代

## 背景
[问题描述]

## 决策
[最终决策]

## 原因
- [理由1]
- [理由2]

## 后果
### 正面
- [好处1]

### 负面
- [代价1]

## 替代方案
- [方案A]: [不选择的原因]
- [方案B]: [不选择的原因]
```

---

## 9. 时间计划

### 9.1 详细时间安排

```
Phase 0: 技术预研 (5天)

Day 1 (周一): DCC 通信方案验证 - WebSocket
├── 上午: 环境准备，阅读文档
├── 下午: WebSocket 基础连接测试
└── 产出: test_websocket_basic.py 运行结果

Day 2 (周二): DCC 通信方案验证 - HTTP + 对比
├── 上午: HTTP API 性能测试
├── 下午: WebSocket vs HTTP 对比分析
└── 产出: 通信方案选型决策

Day 3 (周三): OpenClaw Gateway 集成验证
├── 上午: Gateway 连接和认证测试
├── 下午: MCP Bridge 消息转发测试
└── 产出: Gateway 集成验证报告

Day 4 (周四): 对话面板技术方案验证
├── 上午: 消息流渲染性能测试
├── 下午: 动态表单渲染测试
└── 产出: 前端技术选型确认

Day 5 (周五): 数据存储方案选择 + 总结
├── 上午: JSON vs SQLite 性能测试
├── 下午: 风险评估 + 文档整理
└── 产出: Phase 0 完整报告
```

### 9.2 里程碑

| 里程碑 | 日期 | 交付物 | 验收标准 |
|--------|------|--------|----------|
| M1 | Day 2 | 通信方案选型 | 方案对比报告 |
| M2 | Day 3 | Gateway 验证 | 集成测试通过 |
| M3 | Day 4 | 前端技术确认 | 性能测试达标 |
| M4 | Day 5 | Phase 0 完成 | 本文档完成 |

### 9.3 资源需求

| 资源 | 用途 | 数量 |
|------|------|------|
| 开发机 | 运行测试 | 1 |
| UE 5.7 | DCC 测试 | 1 |
| Maya 2024 | DCC 测试 | 1 |
| ComfyUI | DCC 测试 | 1 |
| OpenClaw Gateway | 集成测试 | 1 |

---

## 附录

### A. 参考文档

1. [architecture-design.md](./architecture-design.md) - 架构设计文档
2. [ROADMAP.md](./ROADMAP.md) - 开发路线图
3. [gateway-forwarding-roadmap.md](../../../../docs/features/gateway-forwarding-roadmap.md) - Gateway 转发流程
4. [comfyui-mcp-integration.md](../../../../docs/features/comfyui-mcp-integration.md) - ComfyUI MCP 集成

### B. 术语表

| 术语 | 说明 |
|------|------|
| DCC | Digital Content Creation，数字内容创作软件 |
| MCP | Model Context Protocol，模型上下文协议 |
| Gateway | OpenClaw 网关服务 |
| Bridge | DCC 与 Gateway 之间的通信桥接层 |
| Skill | AI 操作指南文档 |
| Workflow | ComfyUI 工作流模板 |
| Tool | 用户创建的可复用功能单元 |

### C. 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0 | 2026-04-10 | 初始版本 | 小优 |

---

*本文档为 Phase 0 技术预研的详细指导文档，所有验证结果和决策应记录在此文档中。*
