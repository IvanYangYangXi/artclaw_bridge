"""
test_bridge_dcc.py - bridge_dcc.py 单元测试
=============================================

可在任何 Python 3.9+ 环境中运行（不需要 Maya/Max）。
测试 bridge_core + bridge_dcc 的导入、实例化、配置加载。

运行: python test_bridge_dcc.py
"""

import os
import sys

# 添加必要路径
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
_bridge_pkg = os.path.join(_project_root, "openclaw-mcp-bridge")
_dcc_core = os.path.join(_project_root, "subprojects", "DCCClawBridge", "core")

for p in [_bridge_pkg, _dcc_core]:
    if p not in sys.path:
        sys.path.insert(0, p)


def test_bridge_config_import():
    """测试 bridge_config 导入和配置加载"""
    from bridge_config import load_config, DEFAULT_GATEWAY_URL, PROTOCOL_VERSION
    assert DEFAULT_GATEWAY_URL == "ws://127.0.0.1:18789"
    assert PROTOCOL_VERSION == 3
    config = load_config()  # 可能返回空 dict
    assert isinstance(config, dict)
    print("  ✅ bridge_config import OK")


def test_bridge_core_import():
    """测试 bridge_core 导入和类实例化"""
    from bridge_core import OpenClawBridge, BridgeLogger

    logger = BridgeLogger()
    logger.info("test message")

    bridge = OpenClawBridge(logger=logger)
    assert bridge.is_connected() == False
    assert bridge.gateway_url.startswith("ws://")
    print("  ✅ bridge_core import + instantiation OK")


def test_bridge_diagnostics_import():
    """测试 bridge_diagnostics 导入"""
    from bridge_diagnostics import diagnose_connection
    # 不实际运行诊断（需要 Gateway），只验证导入
    assert callable(diagnose_connection)
    print("  ✅ bridge_diagnostics import OK")


def test_bridge_dcc_import():
    """测试 bridge_dcc 导入和 Manager 实例化"""
    from bridge_dcc import DCCBridgeManager, connect, disconnect, is_connected

    manager = DCCBridgeManager.instance()
    assert manager is not None
    assert manager.is_connected() == False

    # 再次调用 instance() 应返回同一对象
    assert DCCBridgeManager.instance() is manager

    assert callable(connect)
    assert callable(disconnect)
    assert callable(is_connected)
    print("  ✅ bridge_dcc import + Manager singleton OK")


def test_bridge_dcc_no_qt():
    """验证无 Qt 环境下 bridge_dcc 降级工作"""
    from bridge_dcc import DCCBridgeManager
    manager = DCCBridgeManager.instance()
    # signals 可能是 None（无 PySide2）或 _BridgeSignals 实例
    # 两种情况都应该不报错
    print(f"  ✅ signals type: {type(manager.signals).__name__} (None = no Qt, OK)")


if __name__ == "__main__":
    print("=" * 50)
    print("  bridge_dcc.py 集成测试")
    print("=" * 50)

    tests = [
        test_bridge_config_import,
        test_bridge_core_import,
        test_bridge_diagnostics_import,
        test_bridge_dcc_import,
        test_bridge_dcc_no_qt,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1

    print("=" * 50)
    print(f"  结果: {passed} passed, {failed} failed")
    print("=" * 50)
    sys.exit(1 if failed else 0)
