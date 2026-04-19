"""
unity_adapter.py - Unity Editor DCC 适配层
==========================================

实现 BaseDCCAdapter，通过 HTTP 通道与 Unity C# 端通信。
对应 UE 的 ue_adapter.py（在 artclaw_sdk/dcc/ 目录下）。

线程模型：
  Unity 属于「引擎类」DCC（见 sdk-dcc-interface-spec.md D1）。
  主线程调度通过 HTTP → C# CommandServer → EditorApplication.update 实现。
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 回溯到共享适配层基类
_DCC_ROOT = Path(__file__).resolve().parent.parent.parent  # UnityClawBridge/
_ARTCLAW_ROOT = _DCC_ROOT.parent.parent  # artclaw_bridge/

for _p in [str(_ARTCLAW_ROOT / "subprojects" / "DCCClawBridge"), str(_ARTCLAW_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from adapters.base_adapter import BaseDCCAdapter
except ImportError:
    # 独立运行时的占位基类
    from abc import ABC, abstractmethod

    class BaseDCCAdapter(ABC):
        def __init__(self):
            self._exec_namespace: Dict[str, Any] = {}

        def clear_exec_namespace(self) -> None:
            self._exec_namespace.clear()

        @abstractmethod
        def get_software_name(self) -> str: ...
        @abstractmethod
        def get_software_version(self) -> str: ...
        @abstractmethod
        def get_python_version(self) -> str: ...
        @abstractmethod
        def on_startup(self) -> None: ...
        @abstractmethod
        def on_shutdown(self) -> None: ...
        @abstractmethod
        def execute_on_main_thread(self, fn: Callable, *args) -> Any: ...
        @abstractmethod
        def execute_deferred(self, fn: Callable, *args) -> None: ...
        @abstractmethod
        def get_selected_objects(self) -> List[Dict]: ...
        @abstractmethod
        def get_scene_info(self) -> Dict: ...
        @abstractmethod
        def get_current_file(self) -> Optional[str]: ...
        @abstractmethod
        def get_main_window(self) -> Any: ...
        @abstractmethod
        def register_menu(self, menu_name: str, callback: Callable) -> None: ...
        @abstractmethod
        def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict: ...


import logging
import time
import uuid

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

logger = logging.getLogger("artclaw.unity.adapter")

# Unity C# CommandServer 地址
_COMMAND_SERVER_URL = "http://127.0.0.1:8089"
_REQUEST_TIMEOUT = 5.0   # HTTP 提交超时（秒）
_EXEC_TIMEOUT = 60.0     # 等待执行结果超时（秒）
_POLL_INTERVAL = 0.05    # 结果轮询间隔（秒）


class UnityAdapter(BaseDCCAdapter):
    """
    Unity Editor 适配层。
    
    特点：
    - 通过 HTTP 通道（C# CommandServer）向 Unity 主线程提交代码
    - 不需要 Qt 或特定 DCC Python 模块
    - 支持 Unity 2022+ (LTS)
    """

    def __init__(self, command_server_url: str = _COMMAND_SERVER_URL):
        super().__init__()
        self._url = command_server_url
        self._unity_version = "unknown"

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "unity"

    def get_software_version(self) -> str:
        return self._unity_version

    def get_python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # ── 生命周期 ──

    def on_startup(self) -> None:
        """启动时检测 Unity 版本并初始化连接"""
        try:
            result = self._http_get("/health")
            if result:
                self._unity_version = result.get("unity_version", "unknown")
                logger.info(f"Unity CommandServer 已连接 (版本={self._unity_version})")
        except Exception as e:
            logger.warning(f"Unity CommandServer 未响应（正常，Unity 可能尚未启动）: {e}")

        # 初始化 DCCEventManager（Tool Manager 集成）
        try:
            from core.dcc_event_manager import DCCEventManager, set_global_event_manager
            self._event_manager = DCCEventManager(self)
            set_global_event_manager(self._event_manager)
            self._event_manager.load_rules()
            self._event_manager.register_events()
            logger.info("DCCEventManager 初始化完成")
        except Exception as e:
            logger.debug(f"DCCEventManager 初始化跳过（Tool Manager 未运行？）: {e}")

    def on_shutdown(self) -> None:
        try:
            if hasattr(self, "_event_manager") and self._event_manager:
                self._event_manager.unregister_all()
        except Exception:
            pass

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """
        Unity 引擎类：通过 HTTP 通道在主线程执行。
        注意：fn 必须是可序列化为代码字符串的操作，或使用 execute_code 代替。
        直接函数调用不支持跨进程，请用 execute_code 提交代码字符串。
        """
        raise NotImplementedError(
            "Unity 跨进程执行不支持直接函数调用，请使用 execute_code(code_str) 提交代码"
        )

    def execute_deferred(self, fn: Callable, *args) -> None:
        raise NotImplementedError(
            "Unity 跨进程执行不支持直接函数调用，请使用 execute_code(code_str) 提交代码"
        )

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        result = self.execute_code("get_selected_objects()")
        if result.get("success"):
            import json
            try:
                return json.loads(result.get("result", "[]"))
            except Exception:
                return []
        return []

    def get_scene_info(self) -> Dict:
        result = self.execute_code("get_scene_info()")
        if result.get("success"):
            import json
            try:
                return json.loads(result.get("result", "{}"))
            except Exception:
                return {}
        return {"error": result.get("error")}

    def get_current_file(self) -> Optional[str]:
        result = self.execute_code("get_current_file()")
        if result.get("success"):
            return result.get("result")
        return None

    # ── UI 集成 ──

    def get_main_window(self) -> Any:
        """Unity Editor 不暴露 Qt 窗口，返回 None（引擎类标准行为）"""
        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """菜单注册由 C# 端的 MenuItem 属性处理，Python 端 no-op"""
        logger.debug(f"register_menu: {menu_name}（Unity C# 端处理，Python 端 no-op）")

    # ── 代码执行（核心方法）──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        向 Unity C# CommandServer 提交代码并等待执行结果。
        
        Returns:
            {"success": bool, "result": Any, "error": str|None, "output": str}
        """
        if not _HAS_REQUESTS:
            return {"success": False, "error": "缺少依赖: pip install requests", "output": ""}

        exec_id = str(uuid.uuid4())
        payload = {"id": exec_id, "code": code}

        try:
            resp = requests.post(
                f"{self._url}/execute",
                json=payload,
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"命令提交失败: HTTP {resp.status_code}", "output": ""}
        except requests.RequestException as e:
            return {"success": False, "error": f"CommandServer 连接失败: {e}", "output": ""}

        # 轮询结果
        deadline = time.time() + _EXEC_TIMEOUT
        while time.time() < deadline:
            time.sleep(_POLL_INTERVAL)
            try:
                resp = requests.get(
                    f"{self._url}/result/{exec_id}",
                    timeout=_REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("done"):
                        return {
                            "success": not bool(data.get("error")),
                            "result": data.get("result"),
                            "error": data.get("error"),
                            "output": data.get("output", ""),
                        }
            except requests.RequestException:
                pass  # 轮询超时继续重试

        return {"success": False, "error": f"执行超时（{_EXEC_TIMEOUT}s）", "output": ""}

    def batch_execute(self, commands: List[Dict[str, str]]) -> List[Dict]:
        """
        批量执行多条 C# 命令（参考 CoplayDev/unity-mcp batch_execute）。
        比逐条执行快 10-100 倍（减少 HTTP 往返）。

        Args:
            commands: [{"id": "unique_id", "code": "C# 代码"}, ...]
        
        Returns:
            [{"id": ..., "success": bool, "result": Any, "error": str|None, "output": str}, ...]
        """
        if not _HAS_REQUESTS:
            return [{"id": c.get("id"), "success": False, "error": "缺少依赖: pip install requests"} for c in commands]

        # 填充缺失的 id
        for c in commands:
            if not c.get("id"):
                c["id"] = str(uuid.uuid4())

        try:
            resp = requests.post(
                f"{self._url}/batch_execute",
                json=commands,
                timeout=60.0,  # 批量执行允许更长超时
            )
            if resp.status_code != 200:
                return [{"id": c.get("id"), "success": False, "error": f"HTTP {resp.status_code}"} for c in commands]

            results_raw = resp.json().get("results", [])
            results = []
            for r in results_raw:
                results.append({
                    "id": r.get("id"),
                    "success": not bool(r.get("error")),
                    "result": r.get("result"),
                    "error": r.get("error"),
                    "output": r.get("output", ""),
                })
            return results

        except requests.RequestException as e:
            return [{"id": c.get("id"), "success": False, "error": str(e)} for c in commands]

    # ── 内部 HTTP 工具 ──

    def _http_get(self, path: str) -> Optional[Dict]:
        if not _HAS_REQUESTS:
            return None
        resp = requests.get(f"{self._url}{path}", timeout=_REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return None

    # ── 上下文字典（DCC 标准接口 D7）──

    def get_context(self) -> Dict:
        scene_info = self.get_scene_info()
        selected = self.get_selected_objects()
        return {
            "selection": selected,
            "scene_name": scene_info.get("name", ""),
            "file_path": scene_info.get("path"),
            "unity_version": self._unity_version,
        }
