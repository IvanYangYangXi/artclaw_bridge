"""
comfyui_adapter.py - ComfyUI 适配层实现
=========================================

ComfyUI (Python 3.10+, aiohttp web server)

在 ComfyUI 进程内运行（作为自定义节点加载）。
通过 import ComfyUI 内部模块直接操作：
  - nodes: 节点注册表
  - folder_paths: 模型/输出路径
  - execution: 执行引擎
  - server: PromptServer

与 Maya/SD/Blender adapter 同构，提供 run_python 代码执行能力。
ComfyUI 无 Qt/UI、无 undo、无"选中对象"概念。
"""

from __future__ import annotations

import io
import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseDCCAdapter

logger = logging.getLogger("artclaw.comfyui")


def _try_import(module_name: str, default=None):
    """安全导入 ComfyUI 内部模块"""
    try:
        return __import__(module_name)
    except ImportError:
        return default


# 预览图保存目录
_PREVIEW_SAVE_DIR = os.path.join(
    os.path.expanduser("~"), ".artclaw", "comfyui", "previews"
)


def _make_save_preview_func(client):
    """创建 save_preview 辅助函数（注入到 exec 命名空间）。

    支持两种用法:
        save_preview(image_bytes, "label")          # PIL Image 或 bytes
        save_preview("/path/to/image.png", "label") # 文件路径

    自动输出 [IMAGE:path] 标记，让 AI 在返回结果中看到图片。
    """
    def save_preview(image_or_path, label="preview", quality=85):
        """保存图片并输出 [IMAGE:] 标记。

        Args:
            image_or_path: PIL Image, bytes, 或文件路径字符串
            label: 显示标签/文件名
            quality: JPEG 质量 (1-100)

        Returns:
            保存的文件路径，失败返回 None
        """
        import re as _re

        save_dir = _PREVIEW_SAVE_DIR
        os.makedirs(save_dir, exist_ok=True)
        safe_label = _re.sub(r'[^\w\-]', '_', str(label))

        # 情况 1: 文件路径
        if isinstance(image_or_path, str):
            if os.path.isfile(image_or_path):
                print(f"{label}:")
                print(f"[IMAGE:{image_or_path}]")
                return image_or_path
            else:
                print(f"[{label}] 文件不存在: {image_or_path}")
                return None

        # 情况 2: PIL Image
        try:
            # 检查是否是 PIL Image
            if hasattr(image_or_path, 'save') and hasattr(image_or_path, 'size'):
                save_path = os.path.join(save_dir, f"{safe_label}.jpg")
                if image_or_path.mode in ('RGBA', 'P'):
                    image_or_path = image_or_path.convert('RGB')
                image_or_path.save(save_path, "JPEG", quality=quality)
                print(f"{label} ({image_or_path.size[0]}x{image_or_path.size[1]}):")
                print(f"[IMAGE:{save_path}]")
                return save_path
        except Exception as e:
            print(f"[{label}] PIL Image 保存失败: {e}")
            return None

        # 情况 3: bytes
        if isinstance(image_or_path, bytes):
            save_path = os.path.join(save_dir, f"{safe_label}.png")
            with open(save_path, 'wb') as f:
                f.write(image_or_path)
            print(f"{label}:")
            print(f"[IMAGE:{save_path}]")
            return save_path

        print(f"[{label}] 不支持的类型: {type(image_or_path)}")
        return None

    return save_preview


class _ComfyUILib:
    """ComfyUI 辅助库对象，作为 L 变量注入到 exec 命名空间。

    延迟加载 ComfyUI 内部模块，避免导入时序问题。
    """

    @property
    def nodes(self):
        """ComfyUI 节点注册表（NODE_CLASS_MAPPINGS）"""
        import nodes
        return nodes

    @property
    def folder_paths(self):
        """ComfyUI 文件路径管理"""
        import folder_paths
        return folder_paths

    @property
    def execution(self):
        """ComfyUI 执行引擎"""
        try:
            import execution
            return execution
        except ImportError:
            return None

    @property
    def server(self):
        """ComfyUI PromptServer 实例"""
        try:
            import server
            return server.PromptServer.instance if hasattr(server, 'PromptServer') else None
        except ImportError:
            return None

    @property
    def model_management(self):
        """ComfyUI 模型管理（GPU/VRAM 等）"""
        try:
            import comfy.model_management
            return comfy.model_management
        except ImportError:
            return None


class ComfyUIAdapter(BaseDCCAdapter):
    """ComfyUI DCC 适配层

    在 ComfyUI 进程内运行，通过 import 直接访问 ComfyUI 内部模块。
    MCP Server 在独立线程运行 WebSocket，代码执行直接在该线程 exec()。

    与其他 DCC 的关键差异:
      - 无 Qt/UI（Web 前端）
      - 无 undo（ComfyUI 没有撤销概念）
      - 无"选中对象"（S 始终为空列表）
      - 无"当前文件"（W 始终为 None）
      - 提供 client (ComfyUIClient) 和 submit_workflow 便捷函数
    """

    def __init__(self, comfyui_url: str = "http://127.0.0.1:8188"):
        super().__init__()
        self._comfyui_url = comfyui_url
        self._lib = _ComfyUILib()

        # 延迟初始化 client（避免循环导入）
        self._client = None

    def _get_client(self):
        """延迟初始化 ComfyUIClient"""
        if self._client is None:
            from core.comfyui_client import ComfyUIClient
            self._client = ComfyUIClient(self._comfyui_url)
        return self._client

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "comfyui"

    def get_software_version(self) -> str:
        """返回 ComfyUI 版本号"""
        # 尝试多种方式获取版本
        try:
            from comfyui_version import __version__
            return str(__version__)
        except ImportError:
            pass

        try:
            # 某些版本通过 comfy.cli_args 暴露版本
            import comfy.cli_args
            if hasattr(comfy.cli_args, 'version'):
                return str(comfy.cli_args.version)
        except (ImportError, AttributeError):
            pass

        # 降级: 返回 "unknown"
        return "unknown"

    def get_python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # ── 生命周期 ──

    def on_startup(self) -> None:
        """启动时调用：设置 DCC 名称 + 启动 MCP Server"""
        logger.info("ArtClaw: ComfyUI adapter startup")

        # 设置 DCC 名称
        try:
            from core.bridge_dcc import DCCBridgeManager
            DCCBridgeManager.set_dcc_name("comfyui")
        except Exception:
            pass

        # MCP Server 由 startup.py 启动，这里不重复启动

    def on_shutdown(self) -> None:
        """关闭时调用：停止 MCP Server"""
        logger.info("ArtClaw: ComfyUI adapter shutdown")

        try:
            from core.mcp_server import stop_mcp_server
            stop_mcp_server()
        except Exception:
            pass

        try:
            from core.bridge_dcc import DCCBridgeManager
            manager = DCCBridgeManager.instance()
            if manager.is_connected():
                manager.disconnect()
        except Exception:
            pass

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """直接执行。

        ComfyUI 的自定义节点代码运行在服务器线程中，
        没有严格的"主线程"限制（不像 Maya/SD 的 Qt 主线程要求）。
        exec 代码可以直接在 MCP Server 线程执行。
        """
        return fn(*args)

    def execute_deferred(self, fn: Callable, *args) -> None:
        """延迟执行（直接调用，ComfyUI 无 QTimer 调度需求）"""
        if args:
            fn(*args)
        else:
            fn()

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        """ComfyUI 无"选中对象"概念，返回空列表"""
        return []

    def get_scene_info(self) -> Dict:
        """返回 ComfyUI 系统信息"""
        info: Dict[str, Any] = {
            "type": "comfyui",
            "url": self._comfyui_url,
        }

        # 尝试获取 GPU/VRAM 信息
        try:
            mm = self._lib.model_management
            if mm:
                info["vram_total_mb"] = round(mm.get_total_memory() / (1024 * 1024))
                info["vram_free_mb"] = round(mm.get_free_memory() / (1024 * 1024))
        except Exception:
            pass

        # 尝试通过 HTTP API 获取系统统计
        try:
            client = self._get_client()
            stats = client.get_system_stats()
            info["system_stats"] = stats
        except Exception:
            pass

        # 尝试获取队列状态
        try:
            client = self._get_client()
            queue_info = client.get_queue()
            info["queue_running"] = len(queue_info.get("queue_running", []))
            info["queue_pending"] = len(queue_info.get("queue_pending", []))
        except Exception:
            pass

        return info

    def get_current_file(self) -> Optional[str]:
        """ComfyUI 无"当前文件"概念，返回 None"""
        return None

    # ── UI 集成（ComfyUI 无 Qt UI） ──

    def get_main_window(self) -> Any:
        """ComfyUI 是 Web UI，无 Qt 主窗口"""
        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """ComfyUI 无菜单系统，跳过"""
        logger.debug("ArtClaw: register_menu — ComfyUI 无菜单，跳过")

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        在 ComfyUI 进程内执行 Python 代码。

        使用持久化命名空间：跨调用保持用户定义的变量。
        每次调用时 DCC 上下文变量会刷新为最新值。

        上下文变量:
            S = [] (无选中概念)
            W = None (无当前文件)
            L = ComfyUI 辅助库（L.nodes, L.folder_paths, L.execution 等）
            client = ComfyUIClient 实例（HTTP API 封装）
            submit_workflow = 便捷函数（提交 workflow 并等待结果）
            save_preview = 图片预览函数（输出 [IMAGE:] 标记）
        """
        client = self._get_client()

        # ── 持久化命名空间：刷新 DCC 上下文变量 ──
        ns = self._exec_namespace
        ns.update({
            "__builtins__": __builtins__,
            "S": [],
            "W": None,
            "L": self._lib,
            "client": client,
            "submit_workflow": client.submit_and_wait,
            "save_preview": _make_save_preview_func(client),
        })

        # 直接注入常用 ComfyUI 模块（方便 agent 使用）
        try:
            import nodes
            ns["nodes"] = nodes
        except ImportError:
            pass

        try:
            import folder_paths
            ns["folder_paths"] = folder_paths
        except ImportError:
            pass

        if context:
            ns.update(context)

        # 清除上次的 result
        ns.pop("result", None)

        # 捕获 stdout
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture
            # ComfyUI 无 undo，直接执行
            exec(code, ns)

            output = stdout_capture.getvalue()
            result = ns.get("result")

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
