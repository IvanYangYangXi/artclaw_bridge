"""
comfyui_client.py - ComfyUI HTTP API 客户端
==============================================

通过 urllib.request 与 ComfyUI REST API 通信（同步调用）。
移植自 MeiGen-AI-Design-MCP 的 ComfyUIProvider (TypeScript)。

ComfyUI REST API:
  POST /prompt          — 提交 workflow
  GET  /history/{id}    — 查询执行历史
  GET  /view            — 下载输出图片
  POST /upload/image    — 上传图片
  GET  /models/{type}   — 列出模型
  GET  /system_stats    — 系统信息
  GET  /queue           — 队列状态
  POST /interrupt       — 取消当前任务
  GET  /object_info     — 节点类型信息
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("artclaw.comfyui.client")


class ComfyUIClient:
    """ComfyUI HTTP API 同步客户端"""

    def __init__(self, base_url: str = "http://127.0.0.1:8188"):
        self._base_url = base_url.rstrip("/")
        self._client_id = f"artclaw_{os.getpid()}"

    @property
    def base_url(self) -> str:
        return self._base_url

    # ── 内部 HTTP 方法 ──

    def _get(self, path: str, params: Optional[Dict] = None, timeout: float = 30) -> Any:
        """GET 请求，返回解析后的 JSON"""
        url = f"{self._base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise ConnectionError(f"ComfyUI 连接失败 ({url}): {e}") from e

    def _get_bytes(self, path: str, params: Optional[Dict] = None, timeout: float = 60) -> bytes:
        """GET 请求，返回原始字节"""
        url = f"{self._base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.URLError as e:
            raise ConnectionError(f"ComfyUI 连接失败 ({url}): {e}") from e

    def _post_json(self, path: str, data: Any, timeout: float = 30) -> Any:
        """POST JSON 请求，返回解析后的 JSON"""
        url = f"{self._base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.URLError as e:
            raise ConnectionError(f"ComfyUI 请求失败 ({url}): {e}") from e

    def _post_multipart(self, path: str, fields: Dict[str, Any],
                        files: Dict[str, tuple], timeout: float = 60) -> Any:
        """POST multipart/form-data 请求（用于上传图片）"""
        import uuid as _uuid
        boundary = f"----ArtClawBoundary{_uuid.uuid4().hex}"

        body_parts = []

        # 普通字段
        for key, value in fields.items():
            body_parts.append(f"--{boundary}\r\n".encode())
            body_parts.append(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            )
            body_parts.append(f"{value}\r\n".encode())

        # 文件字段
        for key, (filename, data, content_type) in files.items():
            body_parts.append(f"--{boundary}\r\n".encode())
            body_parts.append(
                f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode()
            )
            body_parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
            body_parts.append(data)
            body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(body_parts)

        url = f"{self._base_url}{path}"
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.URLError as e:
            raise ConnectionError(f"ComfyUI 上传失败 ({url}): {e}") from e

    # ── 公开 API ──

    def check_connection(self) -> Dict:
        """检查 ComfyUI 是否可达，返回系统信息"""
        try:
            stats = self.get_system_stats()
            return {
                "connected": True,
                "system_stats": stats,
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
            }

    def submit_prompt(self, workflow: Dict) -> str:
        """提交 workflow 到 ComfyUI 执行队列，返回 prompt_id。

        Args:
            workflow: ComfyUI workflow JSON（API 格式，节点 ID 为 key）

        Returns:
            prompt_id 字符串
        """
        payload = {
            "prompt": workflow,
            "client_id": self._client_id,
        }
        result = self._post_json("/prompt", payload)
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            error_msg = result.get("error", result.get("node_errors", "未知错误"))
            raise RuntimeError(f"ComfyUI 拒绝 workflow: {error_msg}")
        logger.info(f"Workflow submitted: {prompt_id}")
        return prompt_id

    def poll_history(self, prompt_id: str, timeout: float = 300,
                     poll_interval: float = 1.0) -> Dict:
        """轮询 /history/{prompt_id} 直到执行完成或超时。

        Args:
            prompt_id: submit_prompt 返回的 ID
            timeout: 最大等待秒数
            poll_interval: 轮询间隔秒数

        Returns:
            执行历史 dict（包含 outputs）
        """
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                history = self._get(f"/history/{prompt_id}", timeout=10)
            except Exception:
                time.sleep(poll_interval)
                continue

            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("completed", False) or status.get("status_str") == "success":
                    logger.info(f"Workflow completed: {prompt_id}")
                    return entry
                # 检查是否有错误
                if status.get("status_str") == "error":
                    error_msgs = []
                    for node_id, node_err in entry.get("outputs", {}).items():
                        if isinstance(node_err, dict) and "error" in node_err:
                            error_msgs.append(f"Node {node_id}: {node_err['error']}")
                    raise RuntimeError(
                        f"Workflow 执行失败: {'; '.join(error_msgs) or status}"
                    )

            time.sleep(poll_interval)

        raise TimeoutError(f"Workflow 执行超时 ({timeout}s): {prompt_id}")

    def get_image(self, filename: str, subfolder: str = "",
                  img_type: str = "output") -> bytes:
        """下载 ComfyUI 输出的图片。

        Args:
            filename: 图片文件名
            subfolder: 子目录（通常为空）
            img_type: "output" | "input" | "temp"

        Returns:
            图片原始字节
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": img_type,
        }
        return self._get_bytes("/view", params=params)

    def upload_image(self, image_bytes: bytes, filename: str,
                     subfolder: str = "", img_type: str = "input",
                     overwrite: bool = True) -> str:
        """上传图片到 ComfyUI（用于 LoadImage 节点等）。

        Args:
            image_bytes: 图片数据
            filename: 目标文件名
            subfolder: 子目录
            img_type: "input" | "temp"
            overwrite: 是否覆盖同名文件

        Returns:
            上传后的文件名（可能被 ComfyUI 重命名）
        """
        # 根据扩展名判断 MIME 类型
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        content_type = mime_map.get(ext, "image/png")

        fields = {
            "subfolder": subfolder,
            "type": img_type,
            "overwrite": str(overwrite).lower(),
        }
        files = {
            "image": (filename, image_bytes, content_type),
        }
        result = self._post_multipart("/upload/image", fields, files)
        uploaded_name = result.get("name", filename)
        logger.info(f"Image uploaded: {uploaded_name}")
        return uploaded_name

    def list_models(self, model_type: str = "checkpoints") -> List[str]:
        """列出指定类型的模型文件。

        Args:
            model_type: "checkpoints" | "loras" | "vae" | "controlnet" 等

        Returns:
            模型文件名列表
        """
        try:
            return self._get(f"/models/{model_type}")
        except Exception:
            # 某些版本不支持 /models API，降级到 object_info
            logger.debug(f"/models/{model_type} 不可用，返回空列表")
            return []

    def get_system_stats(self) -> Dict:
        """获取 ComfyUI 系统信息（GPU/VRAM/设备等）"""
        return self._get("/system_stats")

    def get_queue(self) -> Dict:
        """获取当前队列状态"""
        return self._get("/queue")

    def cancel_current(self) -> None:
        """中断当前正在执行的任务"""
        self._post_json("/interrupt", {})
        logger.info("Current task interrupted")

    def clear_queue(self) -> None:
        """清空执行队列"""
        self._post_json("/queue", {"clear": True})
        logger.info("Queue cleared")

    def get_object_info(self, class_type: Optional[str] = None) -> Dict:
        """获取节点类型信息。

        Args:
            class_type: 如果指定，只返回该类型的信息；否则返回全部

        Returns:
            节点类型定义 dict
        """
        if class_type:
            return self._get(f"/object_info/{class_type}")
        return self._get("/object_info")

    def submit_and_wait(self, workflow: Dict, timeout: float = 300) -> Dict:
        """提交 workflow 并等待完成，返回输出信息。

        便捷方法：submit_prompt + poll_history + 解析输出图片路径。

        Args:
            workflow: ComfyUI workflow JSON
            timeout: 最大等待秒数

        Returns:
            {
                "prompt_id": str,
                "outputs": dict,    # 原始输出
                "images": list,     # 输出图片信息列表 [{filename, subfolder, type}]
            }
        """
        prompt_id = self.submit_prompt(workflow)
        history = self.poll_history(prompt_id, timeout=timeout)

        # 提取输出图片信息
        images = []
        outputs = history.get("outputs", {})
        for node_id, node_output in outputs.items():
            if isinstance(node_output, dict) and "images" in node_output:
                for img_info in node_output["images"]:
                    images.append({
                        "filename": img_info.get("filename", ""),
                        "subfolder": img_info.get("subfolder", ""),
                        "type": img_info.get("type", "output"),
                        "node_id": node_id,
                    })

        return {
            "prompt_id": prompt_id,
            "outputs": outputs,
            "images": images,
        }
