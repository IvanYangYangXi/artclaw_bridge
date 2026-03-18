"""
test_mcp_client.py - MCP WebSocket 测试客户端
===============================================

在 UE 编辑器外部运行，用于测试 MCP 服务器的连接和消息收发。

用法:
    python test_mcp_client.py                    # 交互模式
    python test_mcp_client.py --port 8080        # 指定端口
    python test_mcp_client.py --auto             # 自动运行全部测试
"""

import asyncio
import json
import sys
import argparse

try:
    import websockets
except ImportError:
    print("需要安装 websockets: pip install websockets")
    sys.exit(1)


JSONRPC_VERSION = "2.0"
_request_id = 0


def next_id():
    global _request_id
    _request_id += 1
    return _request_id


def make_request(method: str, params: dict = None) -> str:
    msg = {
        "jsonrpc": JSONRPC_VERSION,
        "id": next_id(),
        "method": method,
    }
    if params:
        msg["params"] = params
    return json.dumps(msg)


def make_notification(method: str, params: dict = None) -> str:
    msg = {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
    }
    if params:
        msg["params"] = params
    return json.dumps(msg)


def pretty(data) -> str:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return data
    return json.dumps(data, indent=2, ensure_ascii=False)


# ============================================================================
# 自动测试
# ============================================================================

async def run_auto_tests(uri: str):
    """自动运行全部测试用例"""
    print(f"\n{'='*60}")
    print(f"MCP WebSocket 自动测试")
    print(f"目标: {uri}")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0

    try:
        async with websockets.connect(uri) as ws:
            # --- 测试 1: initialize 握手 ---
            print("[TEST 1] initialize 握手...")
            req = make_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test_client", "version": "1.0"}
            })
            await ws.send(req)
            resp = json.loads(await ws.recv())

            if "result" in resp and "protocolVersion" in resp["result"]:
                print(f"  ✅ 握手成功: protocol={resp['result']['protocolVersion']}")
                print(f"     serverInfo={resp['result'].get('serverInfo', {})}")
                print(f"     capabilities={resp['result'].get('capabilities', {})}")
                passed += 1
            else:
                print(f"  ❌ 握手失败: {pretty(resp)}")
                failed += 1

            # --- 测试 2: initialized 通知 ---
            print("\n[TEST 2] initialized 通知...")
            notif = make_notification("initialized", {})
            await ws.send(notif)
            # 通知没有响应，等待短暂时间确认无异常
            await asyncio.sleep(0.3)
            print(f"  ✅ initialized 通知已发送 (无需响应)")
            passed += 1

            # --- 测试 3: ping ---
            print("\n[TEST 3] ping 心跳...")
            req = make_request("ping", {})
            await ws.send(req)
            resp = json.loads(await ws.recv())

            if "result" in resp:
                print(f"  ✅ ping 响应正常")
                passed += 1
            else:
                print(f"  ❌ ping 失败: {pretty(resp)}")
                failed += 1

            # --- 测试 4: tools/list ---
            print("\n[TEST 4] tools/list 获取工具列表...")
            req = make_request("tools/list", {})
            await ws.send(req)
            resp = json.loads(await ws.recv())

            if "result" in resp and "tools" in resp["result"]:
                tools = resp["result"]["tools"]
                print(f"  ✅ 获取到 {len(tools)} 个工具")
                for t in tools:
                    print(f"     - {t.get('name', '?')}: {t.get('description', '')[:60]}")
                passed += 1
            else:
                print(f"  ❌ tools/list 失败: {pretty(resp)}")
                failed += 1

            # --- 测试 5: resources/list ---
            print("\n[TEST 5] resources/list 获取资源列表...")
            req = make_request("resources/list", {})
            await ws.send(req)
            resp = json.loads(await ws.recv())

            if "result" in resp and "resources" in resp["result"]:
                resources = resp["result"]["resources"]
                print(f"  ✅ 获取到 {len(resources)} 个资源")
                passed += 1
            else:
                print(f"  ❌ resources/list 失败: {pretty(resp)}")
                failed += 1

            # --- 测试 6: 不存在的方法 ---
            print("\n[TEST 6] 调用不存在的方法...")
            req = make_request("nonexistent/method", {})
            await ws.send(req)
            resp = json.loads(await ws.recv())

            if "error" in resp and resp["error"]["code"] == -32601:
                print(f"  ✅ 正确返回 Method not found 错误")
                passed += 1
            else:
                print(f"  ❌ 期望错误响应，实际: {pretty(resp)}")
                failed += 1

            # --- 测试 7: 无效 JSON ---
            print("\n[TEST 7] 发送无效 JSON...")
            await ws.send("not valid json {{{")
            resp = json.loads(await ws.recv())

            if "error" in resp and resp["error"]["code"] == -32700:
                print(f"  ✅ 正确返回 Parse error")
                passed += 1
            else:
                print(f"  ❌ 期望解析错误，实际: {pretty(resp)}")
                failed += 1

            # --- 测试 8: run_ue_python 简单执行 ---
            print("\n[TEST 8] run_ue_python 执行 print('Hello')...")
            req = make_request("tools/call", {
                "name": "run_ue_python",
                "arguments": {"code": "print('Hello from MCP test')"}
            })
            await ws.send(req)
            resp = json.loads(await ws.recv())
            if "result" in resp and not resp["result"].get("isError", True):
                content = resp["result"]["content"][0]["text"]
                result_data = json.loads(content)
                if result_data.get("success"):
                    print(f"  ✅ 执行成功, output='{result_data.get('output', '').strip()}'")
                    passed += 1
                else:
                    print(f"  ❌ 执行失败: {result_data.get('error', '?')}")
                    failed += 1
            else:
                print(f"  ❌ 调用失败: {pretty(resp)}")
                failed += 1

            # --- 测试 9: run_ue_python 表达式返回值 ---
            print("\n[TEST 9] run_ue_python 执行表达式 1+1...")
            req = make_request("tools/call", {
                "name": "run_ue_python",
                "arguments": {"code": "1 + 1"}
            })
            await ws.send(req)
            resp = json.loads(await ws.recv())
            if "result" in resp:
                content = resp["result"]["content"][0]["text"]
                result_data = json.loads(content)
                if result_data.get("success") and result_data.get("result") == 2:
                    print(f"  ✅ 表达式返回值: {result_data['result']}")
                    passed += 1
                else:
                    print(f"  ❌ 返回值异常: {result_data}")
                    failed += 1
            else:
                print(f"  ❌ 调用失败: {pretty(resp)}")
                failed += 1

            # --- 测试 10: run_ue_python 错误捕获 ---
            print("\n[TEST 10] run_ue_python 错误代码...")
            req = make_request("tools/call", {
                "name": "run_ue_python",
                "arguments": {"code": "raise ValueError('test error')"}
            })
            await ws.send(req)
            resp = json.loads(await ws.recv())
            if "result" in resp:
                content = resp["result"]["content"][0]["text"]
                result_data = json.loads(content)
                if not result_data.get("success") and "ValueError" in (result_data.get("error") or ""):
                    print(f"  ✅ 错误被捕获: ValueError")
                    passed += 1
                else:
                    print(f"  ❌ 错误未正确捕获: {result_data}")
                    failed += 1
            else:
                failed += 1

            # --- 测试 11: Static Guard 拦截 ---
            print("\n[TEST 11] Static Guard 拦截 os.system...")
            req = make_request("tools/call", {
                "name": "run_ue_python",
                "arguments": {"code": "import os; os.system('echo hacked')"}
            })
            await ws.send(req)
            resp = json.loads(await ws.recv())
            if "result" in resp:
                content = resp["result"]["content"][0]["text"]
                result_data = json.loads(content)
                if not result_data.get("success") and result_data.get("security", {}).get("blocked"):
                    print(f"  ✅ 危险代码被 Static Guard 拦截!")
                    passed += 1
                else:
                    print(f"  ❌ 危险代码未被拦截: {result_data}")
                    failed += 1
            else:
                failed += 1

            # --- 测试 12: 上下文注入 S/W/L ---
            print("\n[TEST 12] 上下文注入 (S/W/L 变量)...")
            req = make_request("tools/call", {
                "name": "run_ue_python",
                "arguments": {"code": "result = {'S_type': str(type(S)), 'W_type': str(type(W)), 'L_name': L.__name__}"}
            })
            await ws.send(req)
            resp = json.loads(await ws.recv())
            if "result" in resp:
                content = resp["result"]["content"][0]["text"]
                result_data = json.loads(content)
                if result_data.get("success") and result_data.get("result"):
                    ctx = result_data["result"]
                    print(f"  ✅ S={ctx.get('S_type')}, W={ctx.get('W_type')}, L={ctx.get('L_name')}")
                    passed += 1
                else:
                    print(f"  ❌ 上下文获取失败: {result_data}")
                    failed += 1
            else:
                failed += 1

            # --- 测试 13: 连接保持 ---
            print("\n[TEST 13] 连接保持 (等待2秒)...")
            await asyncio.sleep(2)
            req = make_request("ping", {})
            await ws.send(req)
            resp = json.loads(await ws.recv())
            if "result" in resp:
                print(f"  ✅ 连接仍然存活")
                passed += 1
            else:
                print(f"  ❌ 连接可能已断开")
                failed += 1

    except ConnectionRefusedError:
        print(f"\n❌ 连接被拒绝！请确认 MCP 服务器已在 {uri} 上启动。")
        print(f"   在 UE 编辑器中检查 Output Log 是否有 'MCP Server started' 日志。")
        failed += 1
    except Exception as e:
        print(f"\n❌ 测试异常: {type(e).__name__}: {e}")
        failed += 1

    # 汇总
    print(f"\n{'='*60}")
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {passed + failed} 项")
    print(f"{'='*60}")
    return failed == 0


# ============================================================================
# 交互模式
# ============================================================================

async def run_interactive(uri: str):
    """交互模式：手动发送消息"""
    print(f"\n{'='*60}")
    print(f"MCP WebSocket 交互式测试客户端")
    print(f"目标: {uri}")
    print(f"{'='*60}")
    print(f"\n可用命令:")
    print(f"  init       - 执行 initialize + initialized 握手")
    print(f"  ping       - 发送 ping")
    print(f"  tools      - 获取 tools/list")
    print(f"  resources  - 获取 resources/list")
    print(f"  call <name> <json_args> - 调用 tool")
    print(f"  raw <json> - 发送原始 JSON")
    print(f"  quit       - 退出")
    print()

    try:
        async with websockets.connect(uri) as ws:
            print(f"✅ 已连接到 {uri}\n")

            while True:
                try:
                    cmd = input("mcp> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if not cmd:
                    continue

                if cmd == "quit" or cmd == "exit":
                    break

                elif cmd == "init":
                    # initialize
                    req = make_request("initialize", {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "interactive_client", "version": "1.0"}
                    })
                    await ws.send(req)
                    resp = await ws.recv()
                    print(f"<< {pretty(resp)}")

                    # initialized
                    notif = make_notification("initialized", {})
                    await ws.send(notif)
                    print("<< (initialized 通知已发送, 无响应)")

                elif cmd == "ping":
                    req = make_request("ping", {})
                    await ws.send(req)
                    resp = await ws.recv()
                    print(f"<< {pretty(resp)}")

                elif cmd == "tools":
                    req = make_request("tools/list", {})
                    await ws.send(req)
                    resp = await ws.recv()
                    print(f"<< {pretty(resp)}")

                elif cmd == "resources":
                    req = make_request("resources/list", {})
                    await ws.send(req)
                    resp = await ws.recv()
                    print(f"<< {pretty(resp)}")

                elif cmd.startswith("call "):
                    parts = cmd[5:].split(" ", 1)
                    tool_name = parts[0]
                    args = json.loads(parts[1]) if len(parts) > 1 else {}
                    req = make_request("tools/call", {
                        "name": tool_name,
                        "arguments": args,
                    })
                    await ws.send(req)
                    resp = await ws.recv()
                    print(f"<< {pretty(resp)}")

                elif cmd.startswith("raw "):
                    raw = cmd[4:]
                    await ws.send(raw)
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        print(f"<< {pretty(resp)}")
                    except asyncio.TimeoutError:
                        print("<< (3秒无响应，可能是通知消息)")

                else:
                    print(f"未知命令: {cmd}")

    except ConnectionRefusedError:
        print(f"\n❌ 连接被拒绝！请确认 MCP 服务器已在 {uri} 上启动。")
    except Exception as e:
        print(f"\n❌ 连接错误: {type(e).__name__}: {e}")


# ============================================================================
# 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="MCP WebSocket 测试客户端")
    parser.add_argument("--host", default="localhost", help="服务器地址 (默认: localhost)")
    parser.add_argument("--port", type=int, default=8080, help="服务器端口 (默认: 8080)")
    parser.add_argument("--auto", action="store_true", help="自动运行全部测试")
    args = parser.parse_args()

    uri = f"ws://{args.host}:{args.port}"

    if args.auto:
        success = asyncio.run(run_auto_tests(uri))
        sys.exit(0 if success else 1)
    else:
        asyncio.run(run_interactive(uri))


if __name__ == "__main__":
    main()
