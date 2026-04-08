"""
substance_designer_adapter.py - Substance Designer 适配层实现
================================================================

Substance Designer 2021+ (Python 3.6+, PySide2/Qt 5)

SD Python API 模块为 ``sd``，严格单线程——所有 API 调用必须在主线程执行
且通过 threading.Lock 保护，防止并发访问。

SD 不提供 undo group API，因此 execute_code 不做 undo 包装。
"""

from __future__ import annotations

import io
import logging
import queue
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseDCCAdapter

logger = logging.getLogger("artclaw.substance_designer")


def _require_sd():
    """延迟 import sd 模块，仅在 Substance Designer 环境中可用"""
    import sd

    app = sd.getContext().getSDApplication()
    return sd, app


# 预导入的 sd.api 子模块缓存（在首次调用时填充，避免 exec 中 import 死锁）
_SD_API_CACHE: dict = {}


def _ensure_sd_api_imports():
    """
    预导入常用 sd.api 子模块到缓存。

    SD 的模块 import 在 exec() 中可能因为线程锁竞争超时，
    但在普通函数调用上下文中是安全的。
    首次调用时一次性加载，后续直接使用缓存。
    """
    if _SD_API_CACHE:
        return _SD_API_CACHE

    try:
        from sd.api.sdproperty import SDPropertyCategory
        from sd.api.sdbasetypes import float2, float3, float4, ColorRGBA, int2, int3, int4
        from sd.api.sdvaluefloat import SDValueFloat
        from sd.api.sdvalueint import SDValueInt
        from sd.api.sdvaluebool import SDValueBool
        from sd.api.sdvaluestring import SDValueString
        from sd.api.sdvaluefloat2 import SDValueFloat2
        from sd.api.sdvaluefloat3 import SDValueFloat3
        from sd.api.sdvaluefloat4 import SDValueFloat4
        from sd.api.sdvaluecolorrgba import SDValueColorRGBA

        _SD_API_CACHE.update({
            "SDPropertyCategory": SDPropertyCategory,
            "float2": float2, "float3": float3, "float4": float4,
            "ColorRGBA": ColorRGBA,
            "int2": int2, "int3": int3, "int4": int4,
            "SDValueFloat": SDValueFloat,
            "SDValueInt": SDValueInt,
            "SDValueBool": SDValueBool,
            "SDValueString": SDValueString,
            "SDValueFloat2": SDValueFloat2,
            "SDValueFloat3": SDValueFloat3,
            "SDValueFloat4": SDValueFloat4,
            "SDValueColorRGBA": SDValueColorRGBA,
        })

        # 可选的额外模块（某些 SD 版本可能没有）
        for opt_import in [
            ("sd.api.sdvalueint2", "SDValueInt2"),
            ("sd.api.sdvalueint3", "SDValueInt3"),
            ("sd.api.sdvalueint4", "SDValueInt4"),
        ]:
            try:
                mod = __import__(opt_import[0], fromlist=[opt_import[1]])
                _SD_API_CACHE[opt_import[1]] = getattr(mod, opt_import[1])
            except (ImportError, AttributeError):
                pass

        logger.info("ArtClaw: SD API modules pre-imported (%d items)", len(_SD_API_CACHE))
    except Exception as e:
        logger.warning("ArtClaw: Failed to pre-import SD API modules: %s", e)

    return _SD_API_CACHE


class SubstanceDesignerAdapter(BaseDCCAdapter):
    """Substance Designer DCC 适配层"""

    def __init__(self):
        self._panel = None
        self._api_lock = threading.Lock()
        self._main_queue: queue.Queue = queue.Queue()
        self._poll_timer = None
        # 跨调用保持 graph 引用（解决 API 创建的图不是"当前图"问题）
        self._sticky_graph = None

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "substance_designer"

    def get_software_version(self) -> str:
        """返回 SD 版本号"""
        try:
            _sd, app = _require_sd()
            return str(app.getVersion())
        except Exception:
            return "unknown"

    def get_python_version(self) -> str:
        return (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )

    # ── 生命周期 ──

    def on_startup(self) -> None:
        """SD 启动时调用：设置 DCC 名称 + 启动 MCP Server"""
        logger.info("ArtClaw: Substance Designer adapter startup")

        # 预导入 SD API 子模块（避免 exec 中 import 死锁）
        _ensure_sd_api_imports()

        # 设置 DCC 名称（影响 Gateway session key）
        try:
            from core.bridge_dcc import DCCBridgeManager
            DCCBridgeManager.set_dcc_name("substance_designer")
        except Exception:
            pass

        # 启动 MCP Server（独立线程，不阻塞 SD）
        try:
            from core.mcp_server import start_mcp_server
            if start_mcp_server(adapter=self, port=8086):
                logger.info("ArtClaw: MCP Server started on port 8086")
            else:
                logger.warning(
                    "ArtClaw: MCP Server failed to start (will retry on connect)"
                )
        except Exception as e:
            logger.error("ArtClaw: MCP Server startup error: %s", e)

        # 启动主线程队列轮询 timer
        self._start_poll_timer()

    def _start_poll_timer(self) -> None:
        """启动 QTimer 定期消费主线程队列（50ms 间隔）"""
        if self._poll_timer is not None:
            return
        try:
            try:
                from PySide2.QtCore import QTimer
            except ImportError:
                from PySide6.QtCore import QTimer

            self._poll_timer = QTimer()
            self._poll_timer.setInterval(50)
            self._poll_timer.timeout.connect(self._consume_main_queue)
            self._poll_timer.start()
            logger.info("ArtClaw: Main thread poll timer started (50ms)")
        except Exception as e:
            logger.warning("ArtClaw: Failed to start poll timer: %s", e)

    def _consume_main_queue(self) -> None:
        """消费主线程队列中的任务（每次 tick 最多 10 个）"""
        processed = 0
        while not self._main_queue.empty() and processed < 10:
            try:
                fn, args = self._main_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception as e:
                logger.error("Main thread task failed: %s", e, exc_info=True)
            processed += 1

    def on_shutdown(self) -> None:
        """SD 关闭时调用：停止 MCP Server + 断开 Bridge"""
        logger.info("ArtClaw: Substance Designer adapter shutdown")

        # 停止轮询 timer
        if self._poll_timer is not None:
            try:
                self._poll_timer.stop()
            except Exception:
                pass
            self._poll_timer = None

        # 停止 MCP Server
        try:
            from core.mcp_server import stop_mcp_server
            stop_mcp_server()
        except Exception:
            pass

        # 断开 Bridge 连接
        try:
            from core.bridge_dcc import DCCBridgeManager
            manager = DCCBridgeManager.instance()
            if manager.is_connected():
                manager.disconnect()
        except Exception:
            pass

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """
        在 SD 主线程执行函数（API 安全）。

        SD API 严格单线程，通过 _api_lock + _main_queue 轮询调度。
        """
        if threading.current_thread() is threading.main_thread():
            with self._api_lock:
                return fn(*args)

        result_queue: queue.Queue = queue.Queue()

        def _run():
            with self._api_lock:
                try:
                    result_queue.put(("ok", fn(*args)))
                except Exception as e:
                    result_queue.put(("error", e))

        self._main_queue.put((_run, ()))

        try:
            status, value = result_queue.get(timeout=30)
        except queue.Empty:
            raise TimeoutError(
                "execute_on_main_thread: 等待主线程执行超时 (30s)"
            )

        if status == "error":
            raise value
        return value

    def execute_deferred(self, fn: Callable, *args) -> None:
        """延迟到主线程空闲时执行（非阻塞），通过队列调度"""
        self._main_queue.put((fn, args))

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        """
        获取当前图（Graph）中的所有节点。

        SD 没有"选中对象"概念，返回当前活动图的全部节点列表。
        """
        try:
            _sd, app = _require_sd()
            ui_mgr = app.getUIMgr()
            current_graph = ui_mgr.getCurrentGraph()
            if current_graph is None:
                return []

            result = []
            for node in current_graph.getNodes():
                try:
                    definition = node.getDefinition()
                    node_type = definition.getId() if definition else "unknown"
                    result.append({
                        "name": node.getIdentifier(),
                        "long_name": node.getIdentifier(),
                        "type": node_type,
                    })
                except Exception:
                    pass
            return result

        except Exception as e:
            logger.warning("ArtClaw: get_selected_objects failed: %s", e)
            return []

    def get_scene_info(self) -> Dict:
        """
        获取当前包（Package）和图（Graph）信息。

        返回:
            scene_file: 第一个包的文件路径
            package_count: 已加载的用户包数量
            graph_count: 所有包中的图总数
            packages: 包信息列表
        """
        try:
            _sd, app = _require_sd()
            pkg_mgr = app.getPackageMgr()
            user_packages = pkg_mgr.getUserPackages()

            packages_info = []
            total_graphs = 0

            for pkg in user_packages:
                try:
                    file_path = pkg.getFilePath()
                    resources = pkg.getChildrenResources(False)
                    graph_count = len(resources) if resources else 0
                    total_graphs += graph_count
                    packages_info.append({
                        "file_path": file_path,
                        "graph_count": graph_count,
                    })
                except Exception:
                    pass

            # 第一个包的路径作为 scene_file
            scene_file = packages_info[0]["file_path"] if packages_info else "untitled"

            return {
                "scene_file": scene_file,
                "package_count": len(user_packages),
                "graph_count": total_graphs,
                "packages": packages_info,
            }

        except Exception as e:
            logger.warning("ArtClaw: get_scene_info failed: %s", e)
            return {
                "scene_file": "untitled",
                "package_count": 0,
                "graph_count": 0,
                "packages": [],
            }

    def get_current_file(self) -> Optional[str]:
        """获取第一个用户包的文件路径"""
        try:
            _sd, app = _require_sd()
            pkg_mgr = app.getPackageMgr()
            user_packages = pkg_mgr.getUserPackages()
            if user_packages:
                return user_packages[0].getFilePath()
        except Exception:
            pass
        return None

    # ── UI 集成 ──

    def get_main_window(self) -> Any:
        """获取 SD 主窗口（QMainWindow）"""
        try:
            try:
                from PySide2 import QtWidgets
            except ImportError:
                from PySide6 import QtWidgets

            app = QtWidgets.QApplication.instance()
            if app:
                for widget in app.topLevelWidgets():
                    if isinstance(widget, QtWidgets.QMainWindow):
                        return widget
        except Exception:
            pass
        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """
        注册菜单入口（占位）。

        SD 的菜单扩展通过 plugin 机制管理，不在 adapter 内创建。
        """
        logger.info(
            "ArtClaw: register_menu('%s') — SD 菜单由 plugin 管理，跳过",
            menu_name,
        )

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        在 SD 环境中执行 Python 代码。

        上下文变量:
            sd   = sd 模块
            app  = SDApplication 实例
            S    = 当前图的节点列表
            W    = 当前文件路径
            L    = sd 模块（标准 Library 引用）
            graph = 当前活动图（SDGraph 或 None）

        注意: SD 不支持 undo group，代码执行不做 undo 包装。
        """
        with self._api_lock:
            try:
                sd_module, app = _require_sd()
            except Exception as e:
                return {
                    "success": False,
                    "result": None,
                    "error": f"SD API unavailable: {e}",
                    "output": "",
                }

            # 获取当前图和节点
            # 优先级: UI 当前图 > sticky graph (API 创建的图)
            current_graph = None
            current_nodes = []
            try:
                ui_mgr = app.getUIMgr()
                current_graph = ui_mgr.getCurrentGraph()
            except Exception:
                pass

            # Fallback: 使用上次 exec 中 AI 设置的 graph
            if current_graph is None and self._sticky_graph is not None:
                try:
                    # 验证 sticky graph 仍然有效（未被关闭/删除）
                    self._sticky_graph.getIdentifier()
                    current_graph = self._sticky_graph
                    logger.debug("ArtClaw: Using sticky graph: %s",
                                 current_graph.getIdentifier())
                except Exception:
                    self._sticky_graph = None

            if current_graph is not None:
                try:
                    current_nodes = list(current_graph.getNodes())
                except Exception:
                    pass

            # 获取当前文件路径
            file_path = ""
            try:
                pkg_mgr = app.getPackageMgr()
                user_packages = pkg_mgr.getUserPackages()
                if user_packages:
                    file_path = user_packages[0].getFilePath() or ""
            except Exception:
                pass

            # 构建执行环境
            # 预注入变量放 exec_globals，确保 def 内部也能访问（Python exec 的闭包规则）
            exec_globals: Dict[str, Any] = {
                "__builtins__": __builtins__,
                "sd": sd_module,
                "app": app,
                "S": current_nodes,
                "W": file_path,
                "L": sd_module,
                "graph": current_graph,
            }

            # 注入预导入的 SD API 类（避免 exec 中 import 超时）
            api_cache = _ensure_sd_api_imports()
            exec_globals.update(api_cache)

            if context:
                exec_globals.update(context)

            exec_locals: Dict[str, Any] = {}

            # 捕获 stdout
            stdout_capture = io.StringIO()
            old_stdout = sys.stdout

            try:
                sys.stdout = stdout_capture
                # SD 不支持 undo group，直接执行
                exec(code, exec_globals, exec_locals)

                output = stdout_capture.getvalue()
                result = exec_locals.get("result") or exec_globals.get("result")

                # 检测 exec 中是否修改了 graph 变量（AI 创建新图后赋值给 graph）
                new_graph = exec_locals.get("graph") or exec_globals.get("graph")
                if new_graph is not None and new_graph is not current_graph:
                    self._sticky_graph = new_graph
                    logger.info("ArtClaw: Sticky graph updated to: %s",
                                getattr(new_graph, 'getIdentifier', lambda: 'unknown')())

                return {
                    "success": True,
                    "result": result,
                    "error": None,
                    "output": output,
                }

            except Exception as e:
                output = stdout_capture.getvalue()
                return {
                    "success": False,
                    "result": None,
                    "error": f"{type(e).__name__}: {str(e)}",
                    "output": output,
                }

            finally:
                sys.stdout = old_stdout

    # ── 内部方法 ──

    def _open_chat_panel(self):
        """打开 ArtClaw Chat 面板"""
        try:
            from artclaw_ui.chat_panel import show_chat_panel
            self._panel = show_chat_panel(
                parent=self.get_main_window(), adapter=self
            )
        except Exception as e:
            logger.error("ArtClaw: Failed to open Chat Panel: %s", e)
