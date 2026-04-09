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
import os
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


# ── 截图预览辅助函数 ──

_PREVIEW_SAVE_DIR = os.path.join(
    os.path.expanduser("~"), ".openclaw", "workspace-xiaoyou", "sd_captures"
)


def _make_save_preview_func():
    """创建 save_preview 辅助函数（注入到 exec 命名空间）。

    用法:
        save_preview(texture, "label")
        save_preview(texture, "label", scale=2)  # 1/2 大小
        save_preview(node, "label")               # 自动获取第一个输出端口的纹理

    自动：缩放到 1/4 → 保存 jpg → 输出 [IMAGE:path] 标记。
    """
    def save_preview(texture_or_node, label="preview", scale=4, quality=80):
        """保存 SD 纹理缩略图并输出 [IMAGE:] 标记让 AI 看到。

        Args:
            texture_or_node: SDTexture 对象，或 SDNode（自动取第一个输出端口）
            label: 显示标签（也用于文件名）
            scale: 缩小倍数（1=原始, 2=1/2, 4=1/4）默认 4
            quality: JPEG 质量 (1-100) 默认 80
        Returns:
            保存的文件路径，失败返回 None
        """
        import os as _os
        import re as _re

        # 如果传入的是 node，自动获取纹理
        tex = texture_or_node
        node = None
        if hasattr(tex, 'getProperties'):
            # 看起来是 SDNode
            node = tex
            try:
                from sd.api.sdproperty import SDPropertyCategory as _SDPCat
                out_props = node.getProperties(_SDPCat.Output)
                if out_props:
                    val = node.getPropertyValue(out_props[0])
                    if val:
                        tex = val.get()
                    else:
                        print(f"[{label}] 节点无输出值（未 compute？）")
                        return None
                else:
                    print(f"[{label}] 节点无输出端口")
                    return None
            except Exception as e:
                print(f"[{label}] 获取纹理失败: {e}")
                return None

        if tex is None or not hasattr(tex, 'save'):
            print(f"[{label}] 无效的纹理对象")
            return None

        # 准备保存目录和文件名
        save_dir = _PREVIEW_SAVE_DIR
        _os.makedirs(save_dir, exist_ok=True)

        # 清理 label 为合法文件名
        safe_label = _re.sub(r'[^\w\-]', '_', label)
        save_path = _os.path.join(save_dir, f"{safe_label}.jpg")

        # 先保存原始纹理到临时 png
        tmp_path = save_path + ".tmp.png"
        try:
            tex.save(tmp_path)
        except Exception as e:
            print(f"[{label}] 纹理保存失败: {e}")
            return None

        try:
            # 读取原始数据
            with open(tmp_path, 'rb') as f:
                raw = f.read()

            # 尝试用 QImage 缩放 + 转 jpg
            try:
                from PySide2.QtGui import QImage
                from PySide2.QtCore import Qt, QByteArray, QBuffer, QIODevice

                ba = QByteArray(raw)
                img = QImage()
                if img.loadFromData(ba):
                    orig_w, orig_h = img.width(), img.height()
                    if scale > 1:
                        new_w = max(orig_w // scale, 64)
                        new_h = max(orig_h // scale, 64)
                        img = img.scaled(new_w, new_h,
                                         Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation)

                    out_ba = QByteArray()
                    buf = QBuffer(out_ba)
                    buf.open(QIODevice.WriteOnly)
                    img.save(buf, "JPEG", quality)
                    buf.close()

                    with open(save_path, 'wb') as f:
                        f.write(bytes(out_ba.data()))

                    print(f"{label} ({img.width()}x{img.height()}):")
                    print(f"[IMAGE:{save_path}]")
                    return save_path
                # QImage 加载失败，fallback
            except ImportError:
                pass  # 没有 PySide2，fallback

            # Fallback: 直接用原始 png（不缩放）
            fallback_path = _os.path.join(save_dir, f"{safe_label}.png")
            _os.rename(tmp_path, fallback_path)
            tmp_path = None  # 已 rename，不需要 finally 清理
            print(f"{label} (原始大小, 未缩放):")
            print(f"[IMAGE:{fallback_path}]")
            return fallback_path

        finally:
            if tmp_path and _os.path.exists(tmp_path):
                try:
                    _os.remove(tmp_path)
                except OSError:
                    pass

    return save_preview


class SubstanceDesignerAdapter(BaseDCCAdapter):
    """Substance Designer DCC 适配层"""

    # exec 执行超时阈值（秒）：超过此时间认为主线程卡死
    EXEC_TIMEOUT = 30
    # 卡死后恢复探测间隔（秒）
    RECOVERY_PROBE_INTERVAL = 5.0
    # 恢复探测最大尝试次数（超过后放弃自动恢复）
    RECOVERY_MAX_PROBES = 12  # 12 * 5s = 60s

    def __init__(self):
        super().__init__()  # 初始化持久化命名空间
        self._panel = None
        self._api_lock = threading.Lock()
        self._main_queue: queue.Queue = queue.Queue()
        self._poll_timer = None
        # 跨调用保持 graph 引用（解决 API 创建的图不是"当前图"问题）
        self._sticky_graph = None
        # 主线程卡死检测
        self._main_thread_busy = False
        # 主线程冻结标志（watchdog 设置，比 _main_thread_busy 更强）
        self._main_thread_frozen = False
        # watchdog 定时器（在 exec 执行时启动）
        self._watchdog_timer: Optional[threading.Timer] = None
        # 恢复探测计数器
        self._recovery_probe_count = 0
        # 视觉分析检查点计数器：连续多少次 tool call 没有产生 [IMAGE:] 输出
        self._calls_since_image = 0
        # 阈值：超过此数量的非截图调用后开始警告
        self._image_check_threshold = 3

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
        """消费主线程队列中的任务（每次 tick 最多 10 个）。

        注意：此函数在 QTimer 回调中执行（SD 主线程），如果 fn(*args) 卡死，
        整个 SD 主线程会冻结。SD API 的某些操作（如 newNode 传不存在的 ID）
        会永久挂起，这是 SD 的已知 bug，无法从 Python 层面超时中断。
        """
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

    # ── Watchdog：exec 超时检测与自动恢复 ──

    def _start_watchdog(self) -> None:
        """启动 watchdog 定时器，在 EXEC_TIMEOUT 秒后触发卡死检测。"""
        self._cancel_watchdog()
        self._watchdog_timer = threading.Timer(
            self.EXEC_TIMEOUT, self._on_exec_timeout
        )
        self._watchdog_timer.daemon = True
        self._watchdog_timer.start()

    def _cancel_watchdog(self) -> None:
        """取消 watchdog 定时器（exec 正常返回时调用）。"""
        if self._watchdog_timer is not None:
            self._watchdog_timer.cancel()
            self._watchdog_timer = None

    def _on_exec_timeout(self) -> None:
        """Watchdog 触发：exec 执行超过 EXEC_TIMEOUT 秒。

        此时主线程可能卡死。标记 frozen 状态并启动恢复探测。
        frozen 状态下所有新请求会立即返回错误（比等 300s 好得多）。
        """
        if not self._main_thread_busy:
            # exec 已经返回了，只是 watchdog 取消慢了一拍
            return

        self._main_thread_frozen = True
        self._recovery_probe_count = 0
        logger.error(
            "ArtClaw Watchdog: exec 执行超过 %ds，主线程可能卡死。"
            "已标记 frozen 状态，后续请求将快速失败。"
            "开始自动恢复探测...",
            self.EXEC_TIMEOUT,
        )
        # 启动恢复探测循环
        self._schedule_recovery_probe()

    def _schedule_recovery_probe(self) -> None:
        """安排下一次恢复探测。"""
        if self._recovery_probe_count >= self.RECOVERY_MAX_PROBES:
            logger.error(
                "ArtClaw Watchdog: 已探测 %d 次（%ds），主线程仍未恢复。"
                "SD 需要手动重启。",
                self._recovery_probe_count,
                int(self._recovery_probe_count * self.RECOVERY_PROBE_INTERVAL),
            )
            return

        probe_timer = threading.Timer(
            self.RECOVERY_PROBE_INTERVAL, self._do_recovery_probe
        )
        probe_timer.daemon = True
        probe_timer.start()

    def _do_recovery_probe(self) -> None:
        """执行一次恢复探测：往主线程队列放一个心跳任务。

        如果主线程解冻了（SD API 调用最终返回），QTimer 会消费队列，
        心跳任务被执行 → 清除 frozen 状态。
        """
        self._recovery_probe_count += 1

        # 如果 busy 标志已清除，说明 exec 最终返回了
        if not self._main_thread_busy:
            self._main_thread_frozen = False
            logger.info(
                "ArtClaw Watchdog: 主线程已恢复（exec 最终返回）。"
                "frozen 状态已清除。"
            )
            return

        # 尝试通过主线程队列发心跳
        def _heartbeat():
            logger.info(
                "ArtClaw Watchdog: 主线程心跳成功！清除 frozen 状态。"
            )
            self._main_thread_frozen = False
            self._main_thread_busy = False
            if self._api_lock.locked():
                try:
                    self._api_lock.release()
                except RuntimeError:
                    pass  # 不是当前线程持有的锁

        try:
            self._main_queue.put_nowait((_heartbeat, ()))
            logger.debug(
                "ArtClaw Watchdog: 恢复探测 #%d 已入队",
                self._recovery_probe_count,
            )
        except Exception as e:
            logger.error("ArtClaw Watchdog: 探测入队失败: %s", e)

        # 安排下一次探测
        self._schedule_recovery_probe()

    def on_shutdown(self) -> None:
        """SD 关闭时调用：停止 MCP Server + 断开 Bridge"""
        logger.info("ArtClaw: Substance Designer adapter shutdown")

        # 取消 watchdog
        self._cancel_watchdog()

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
        如果前一个操作已阻塞主线程，快速失败而不是无限等待。
        """
        if threading.current_thread() is threading.main_thread():
            if not self._api_lock.acquire(timeout=10):
                raise TimeoutError(
                    "SD API 锁获取超时 (10s)，前一个操作可能仍在执行"
                )
            try:
                return fn(*args)
            finally:
                self._api_lock.release()

        # 快速失败：主线程卡死时不排队
        if self._main_thread_busy:
            raise TimeoutError(
                "SD 主线程被前一个操作阻塞，无法执行"
            )

        result_queue: queue.Queue = queue.Queue()

        def _run():
            if not self._api_lock.acquire(timeout=10):
                result_queue.put(("error", TimeoutError("SD API 锁获取超时")))
                return
            try:
                result_queue.put(("ok", fn(*args)))
            except Exception as e:
                result_queue.put(("error", e))
            finally:
                self._api_lock.release()

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

        使用持久化命名空间：跨调用保持用户定义的变量（节点引用、helper 函数等）。
        每次调用时 DCC 上下文变量（sd/app/S/W/L/graph）会刷新为最新值。

        上下文变量:
            sd   = sd 模块
            app  = SDApplication 实例
            S    = 当前图的节点列表
            W    = 当前文件路径
            L    = sd 模块（标准 Library 引用）
            graph = 当前活动图（SDGraph 或 None）

        注意: SD 不支持 undo group，代码执行不做 undo 包装。
        """
        # 防御性初始化：热加载新代码时旧实例可能缺少新属性
        if not hasattr(self, "_exec_namespace"):
            self._exec_namespace = {"__builtins__": __builtins__}
        if not hasattr(self, "_main_thread_busy"):
            self._main_thread_busy = False
        if not hasattr(self, "_main_thread_frozen"):
            self._main_thread_frozen = False

        # 快速失败：如果主线程已被 watchdog 标记为冻结
        if self._main_thread_frozen:
            return {
                "success": False,
                "result": None,
                "error": (
                    "SD 主线程已冻结（上一个操作超过 %ds 未返回）。"
                    "正在尝试自动恢复，如果持续失败请重启 SD。"
                    % self.EXEC_TIMEOUT
                ),
                "output": "",
            }

        # 快速失败：如果主线程已被前一个操作卡死
        if self._main_thread_busy:
            return {
                "success": False,
                "result": None,
                "error": (
                    "SD 主线程被前一个操作阻塞，无法执行新代码。"
                    "可能是 SD API 挂起（已知 bug），需要重启 SD。"
                ),
                "output": "",
            }

        # 尝试获取 API 锁（带超时，避免无限等待）
        if not self._api_lock.acquire(timeout=10):
            return {
                "success": False,
                "result": None,
                "error": (
                    "SD API 锁获取超时 (10s)，前一个操作可能仍在执行。"
                    "如果持续发生，请重启 SD。"
                ),
                "output": "",
            }

        self._main_thread_busy = True
        self._start_watchdog()
        try:
            return self._execute_code_inner(code, context)
        finally:
            self._cancel_watchdog()
            self._main_thread_busy = False
            self._api_lock.release()

    @staticmethod
    def _validate_graph_outputsize(graph_obj, api_cache: dict,
                                   auto_fix: bool = True) -> Optional[str]:
        """校验图的 $outputsize 是否在合理范围，防止 Cooker 爆内存/卡死。

        SD $outputsize 编码: 值 N → 实际像素 2^(N+8)。
          0 → 256px, 1 → 512px, 2 → 1024px, 3 → 2048px,
          4 → 4096px, 5 → 8192px。
        合理范围: 每个分量 0~5 (256px ~ 8192px)。
        值 0 对于库节点内部图表示"继承父图尺寸"，属于正常默认。

        262144px 的 Cooker 警告对应分量值约 10 (2^18=262144)。

        Args:
            graph_obj: SDGraph 实例
            api_cache: 预导入的 SD API 类缓存
            auto_fix: 是否自动修正为 (2, 2) = 1024²

        Returns:
            警告消息（如有问题）或 None（正常）
        """
        if graph_obj is None:
            return None

        SDPropertyCategory = api_cache.get("SDPropertyCategory")
        SDValueInt2 = api_cache.get("SDValueInt2")
        int2_cls = api_cache.get("int2")
        if not all([SDPropertyCategory, SDValueInt2, int2_cls]):
            return None

        try:
            size_prop = graph_obj.getPropertyFromId(
                "$outputsize", SDPropertyCategory.Input
            )
            if not size_prop:
                return None

            val = graph_obj.getPropertyValue(size_prop)
            if not val:
                return None

            s = val.get()
            if not hasattr(s, "x"):
                return None

            # 合理范围: 0 (256px / 继承) ~ 5 (8192px)
            # 值 0 可能是"继承父图"，不修正
            if 0 <= s.x <= 5 and 0 <= s.y <= 5:
                return None

            graph_id = "unknown"
            try:
                graph_id = graph_obj.getIdentifier()
            except Exception:
                pass

            warning = (
                f"⚠️ 图 '{graph_id}' 的 $outputsize=({s.x},{s.y}) 超出合理范围 "
                f"[0..5]，实际像素约 {2**(s.x+8)}x{2**(s.y+8)}。"
            )

            if auto_fix:
                try:
                    graph_obj.setPropertyValue(
                        size_prop, SDValueInt2.sNew(int2_cls(2, 2))
                    )
                    warning += " 已自动修正为 (2,2)=1024²。"
                    logger.warning("ArtClaw: %s", warning)
                except Exception as fix_err:
                    warning += f" 自动修正失败: {fix_err}"
                    logger.error("ArtClaw: %s", warning)
            else:
                logger.warning("ArtClaw: %s", warning)

            return warning

        except Exception as e:
            logger.debug("ArtClaw: outputsize check failed: %s", e)
            return None

    def _validate_all_graphs_outputsize(self, app, api_cache: dict) -> List[str]:
        """校验所有用户包中所有图的 $outputsize，返回警告列表。"""
        warnings = []
        try:
            pkg_mgr = app.getPackageMgr()
            for pkg in pkg_mgr.getUserPackages():
                try:
                    for res in pkg.getChildrenResources(False):
                        try:
                            w = self._validate_graph_outputsize(
                                res, api_cache, auto_fix=True
                            )
                            if w:
                                warnings.append(w)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception as e:
            logger.debug("ArtClaw: all-graph outputsize check failed: %s", e)
        return warnings

    # ── SDNode 安全 Patch：参数预验证 ──

    _node_patched = False  # 类级标志，只 patch 一次

    @classmethod
    def _install_node_safety_patches(cls, api_cache: dict) -> None:
        """Monkey-patch SDNode 的高频出错方法，添加参数预验证。

        当 AI 传了不存在的属性 ID 时，原生 API 只返回一个裸的
        ``APIException: SDApiError.ItemNotFound``，没有任何上下文。
        Patch 后会：
        1. 调用前用 getPropertyFromId 验证属性是否存在
        2. 不存在时立即抛出友好错误，附带该节点的全部可用属性列表
        3. 存在时透传给原始方法，零额外开销

        仅在 SD 进程内 patch 一次（类级标志），对所有 SDNode 实例生效。
        """
        if cls._node_patched:
            return

        SDPropertyCategory = api_cache.get("SDPropertyCategory")
        if not SDPropertyCategory:
            return

        try:
            from sd.api.sdnode import SDNode
        except ImportError:
            return

        # ── 工具函数：列出节点的属性 ID ──

        def _list_props(node, category) -> List[str]:
            """安全地列出节点在指定分类下的所有属性 ID。"""
            try:
                props = node.getProperties(category)
                if props is None:
                    return []
                return [
                    p.getId() for p in props
                    if not p.getId().startswith("$")
                ]
            except Exception:
                return []

        def _get_node_label(node) -> str:
            """获取节点的可读标签（definition + identifier）。"""
            try:
                defn = node.getDefinition()
                defn_id = defn.getId() if defn else "unknown"
            except Exception:
                defn_id = "unknown"
            try:
                node_id = node.getIdentifier() or ""
            except Exception:
                node_id = ""
            return f"{defn_id}" + (f" ({node_id})" if node_id else "")

        # ── Patch setInputPropertyValueFromId ──

        _orig_setInput = SDNode.setInputPropertyValueFromId

        def _safe_setInputPropertyValueFromId(self_node, prop_id, sd_value):
            # 快速验证：属性是否存在
            check = self_node.getPropertyFromId(
                prop_id, SDPropertyCategory.Input
            )
            if check is None:
                available = _list_props(self_node, SDPropertyCategory.Input)
                label = _get_node_label(self_node)
                raise ValueError(
                    f"节点 [{label}] 没有名为 '{prop_id}' 的输入参数。\n"
                    f"可用的输入参数: {available}\n"
                    f"请检查参数名拼写，或用以下代码查询:\n"
                    f"  for p in node.getProperties(SDPropertyCategory.Input):\n"
                    f"      print(p.getId())"
                )
            return _orig_setInput(self_node, prop_id, sd_value)

        SDNode.setInputPropertyValueFromId = _safe_setInputPropertyValueFromId

        # ── Patch newPropertyConnectionFromId ──

        _orig_newConn = SDNode.newPropertyConnectionFromId

        def _safe_newPropertyConnectionFromId(
            self_node, out_prop_id, target_node, in_prop_id
        ):
            # 验证源节点的输出端口
            out_check = self_node.getPropertyFromId(
                out_prop_id, SDPropertyCategory.Output
            )
            if out_check is None:
                available_out = _list_props(
                    self_node, SDPropertyCategory.Output
                )
                label = _get_node_label(self_node)
                raise ValueError(
                    f"源节点 [{label}] 没有名为 '{out_prop_id}' 的输出端口。\n"
                    f"可用的输出端口: {available_out}"
                )
            # 验证目标节点的输入端口
            in_check = target_node.getPropertyFromId(
                in_prop_id, SDPropertyCategory.Input
            )
            if in_check is None:
                available_in = _list_props(
                    target_node, SDPropertyCategory.Input
                )
                target_label = _get_node_label(target_node)
                raise ValueError(
                    f"目标节点 [{target_label}] 没有名为 '{in_prop_id}' 的输入端口。\n"
                    f"可用的输入端口: {available_in}"
                )
            return _orig_newConn(
                self_node, out_prop_id, target_node, in_prop_id
            )

        SDNode.newPropertyConnectionFromId = _safe_newPropertyConnectionFromId

        # ── Patch SDGraph.newNode（防止永久卡死 SD！）──
        # newNode(definition_id) 传不存在的 ID 会永久挂起 SD 主线程，
        # 这是 SD 的已知 bug。用白名单验证 definition_id 格式。

        try:
            from sd.api.sdgraph import SDGraph

            _orig_newNode = SDGraph.newNode

            # 合法的原子节点前缀 (sbs::compositing:: 命名空间)
            _VALID_PREFIXES = (
                "sbs::compositing::",
                "sbs::function::",
                "sbs::mdl::",
            )

            # 已知的合法原子节点 ID（高频使用的）
            _KNOWN_ATOM_NODES = {
                "sbs::compositing::blend",
                "sbs::compositing::levels",
                "sbs::compositing::normal",
                "sbs::compositing::warp",
                "sbs::compositing::directionalwarp",
                "sbs::compositing::uniform",
                "sbs::compositing::output",
                "sbs::compositing::curve",
                "sbs::compositing::hsl",
                "sbs::compositing::blur",
                "sbs::compositing::sharpen",
                "sbs::compositing::invert",
                "sbs::compositing::transformation",
                "sbs::compositing::gradient",
                "sbs::compositing::emboss",
                "sbs::compositing::edgedetect",
                "sbs::compositing::distance",
                "sbs::compositing::passthrough",
                "sbs::compositing::basecolor_to_linear",
                "sbs::compositing::linear_to_basecolor",
                "sbs::compositing::grayscaleconversion",
                "sbs::compositing::rgba_merge",
                "sbs::compositing::rgba_split",
                "sbs::compositing::channel_shuffle",
                "sbs::compositing::multi_switch",
                "sbs::compositing::multi_switch_grayscale",
                "sbs::compositing::curvature",
                "sbs::compositing::histogramrange",
                "sbs::compositing::histogramselect",
                "sbs::compositing::histogramscan",
                "sbs::compositing::histogramshift",
                "sbs::compositing::highpass",
                "sbs::compositing::lowpass",
                "sbs::compositing::valueprocessor",
                "sbs::compositing::pixelprocessor",
                "sbs::compositing::fxmap",
                "sbs::compositing::input",
                "sbs::compositing::text",
                "sbs::compositing::svg",
                "sbs::compositing::bitmap",
                "sbs::compositing::compinstance",
                "sbs::compositing::switch",
                "sbs::compositing::clamp",
                "sbs::compositing::pow",
                "sbs::compositing::quantize",
                "sbs::compositing::replace_color",
                "sbs::compositing::non_uniform_blur",
                "sbs::compositing::skew",
                "sbs::compositing::mirror",
                "sbs::compositing::safe_transform",
                "sbs::compositing::trap_distort",
            }

            def _safe_newNode(self_graph, definition_id):
                # 基本格式检查
                if not isinstance(definition_id, str):
                    raise ValueError(
                        f"newNode 的 definition_id 必须是字符串，"
                        f"收到: {type(definition_id).__name__}"
                    )
                # 检查是否有合法前缀
                if not any(
                    definition_id.startswith(p) for p in _VALID_PREFIXES
                ):
                    raise ValueError(
                        f"newNode: '{definition_id}' 不是合法的原子节点 ID。\n"
                        f"原子节点 ID 必须以 {_VALID_PREFIXES} 开头。\n"
                        f"如果要创建库节点（噪波/纹理），请用:\n"
                        f"  pkg = pm.loadUserPackage(sbs_path)\n"
                        f"  res = pkg.getChildrenResources(False)[0]\n"
                        f"  node = graph.newInstanceNode(res)"
                    )
                # 如果在白名单里，直接放行
                if definition_id in _KNOWN_ATOM_NODES:
                    return _orig_newNode(self_graph, definition_id)
                # 不在白名单但前缀合法：放行但警告
                logger.warning(
                    "ArtClaw Guard: newNode('%s') 不在已知白名单中，"
                    "如果 SD 卡死请报告此 ID。", definition_id
                )
                return _orig_newNode(self_graph, definition_id)

            SDGraph.newNode = _safe_newNode
            logger.info(
                "ArtClaw: SDGraph.newNode safety patch installed"
            )
        except ImportError:
            logger.debug("ArtClaw: SDGraph import failed, skipping newNode patch")

        cls._node_patched = True
        logger.info(
            "ArtClaw: SDNode safety patches installed "
            "(setInputPropertyValueFromId, newPropertyConnectionFromId)"
        )

    def _execute_code_inner(self, code: str, context: Optional[Dict] = None) -> Dict:
        """execute_code 的内部实现（已持有 _api_lock）。"""
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

        # ── 执行前校验：当前图的 $outputsize ──
        api_cache = _ensure_sd_api_imports()
        pre_warnings = []
        pre_w = self._validate_graph_outputsize(
            current_graph, api_cache, auto_fix=True
        )
        if pre_w:
            pre_warnings.append(pre_w)

        # ── 安装 SDNode 安全 patch（参数预验证）──
        self._install_node_safety_patches(api_cache)

        # ── 持久化命名空间：刷新 DCC 上下文变量 ──
        # 只用一个 dict 作为 exec globals（不传 locals），
        # 这样用户代码中定义的变量直接写入命名空间，跨调用持久保留。
        ns = self._exec_namespace
        ns.update({
            "__builtins__": __builtins__,
            "sd": sd_module,
            "app": app,
            "S": current_nodes,
            "W": file_path,
            "L": sd_module,
            "graph": current_graph,
        })

        # 注入预导入的 SD API 类（避免 exec 中 import 超时）
        # api_cache 已在前置校验时获取
        ns.update(api_cache)

        # 注入截图预览辅助函数（v2.8）
        ns["save_preview"] = _make_save_preview_func()

        if context:
            ns.update(context)

        # 清除上次的 result（避免上次结果被误读）
        ns.pop("result", None)

        # 捕获 stdout
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture
            # SD 不支持 undo group，直接执行
            # 只传 globals=ns，不传 locals，所有定义写入 ns
            exec(code, ns)

            output = stdout_capture.getvalue()
            result = ns.get("result")

            # 检测 exec 中是否修改了 graph 变量（AI 创建新图后赋值给 graph）
            new_graph = ns.get("graph")
            if new_graph is not None and new_graph is not current_graph:
                self._sticky_graph = new_graph
                logger.info("ArtClaw: Sticky graph updated to: %s",
                            getattr(new_graph, 'getIdentifier', lambda: 'unknown')())

            # ── 执行后校验：检查所有图的 $outputsize ──
            # agent 代码可能创建了新图或修改了 outputsize，
            # 在 compute 被触发前拦截异常值
            post_warnings = self._validate_all_graphs_outputsize(
                app, api_cache
            )

            # 合并前置 + 后置警告，追加到输出
            all_warnings = pre_warnings + post_warnings
            if all_warnings:
                warning_text = "\n".join(
                    f"[ArtClaw Guard] {w}" for w in all_warnings
                )
                output = output + "\n" + warning_text if output else warning_text

            # ── 视觉分析检查点计数器（仅材质构建任务触发） ──
            # 启发式判断：代码中包含创建/连线操作 = 正在构建材质图
            _build_keywords = (
                "newNode", "newInstanceNode",
                "newPropertyConnectionFromId",
                "setInputPropertyValueFromId",
            )
            is_build_call = any(kw in code for kw in _build_keywords)

            if "[IMAGE:" in output:
                self._calls_since_image = 0
            elif is_build_call:
                self._calls_since_image += 1

            if (is_build_call
                    and self._calls_since_image >= self._image_check_threshold):
                cp_warning = (
                    f"\n⛔ [ArtClaw] 已连续 {self._calls_since_image} 次构建操作没有截图！"
                    f"\n不看截图就继续=盲做，方向偏差会累积到不可修复！"
                    f"\n立即截图：save_preview(graph.getNodeFromId('最新节点ID'), 'checkpoint')"
                    f"\n如果截图返回空，检查节点是否已连接到 output 节点（SD 只计算到 output 的链路）。"
                )
                output = output + cp_warning if output else cp_warning

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
