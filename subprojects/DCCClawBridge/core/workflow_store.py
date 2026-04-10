"""
workflow_store.py - Workflow 模板 CRUD 管理
=============================================

存储目录: ~/.artclaw/comfyui/workflows/
模板以 JSON 文件保存，文件名即模板名。

用法:
    store = WorkflowStore()
    store.save("txt2img_sdxl", workflow_dict)
    wf = store.load("txt2img_sdxl")
    names = store.list()
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger("artclaw.comfyui.workflow_store")

# 默认存储目录
_DEFAULT_STORE_DIR = os.path.join(
    os.path.expanduser("~"), ".artclaw", "comfyui", "workflows"
)


class WorkflowStore:
    """Workflow 模板 CRUD 管理器"""

    def __init__(self, store_dir: Optional[str] = None):
        self._store_dir = store_dir or _DEFAULT_STORE_DIR
        os.makedirs(self._store_dir, exist_ok=True)
        logger.info(f"WorkflowStore: {self._store_dir}")

    @property
    def store_dir(self) -> str:
        return self._store_dir

    def _path_for(self, name: str) -> str:
        """获取模板文件路径（自动补 .json 后缀）"""
        if not name.endswith(".json"):
            name = f"{name}.json"
        return os.path.join(self._store_dir, name)

    def list(self) -> List[str]:
        """列出所有模板名称（不含 .json 后缀）"""
        try:
            files = os.listdir(self._store_dir)
            return sorted(
                os.path.splitext(f)[0]
                for f in files
                if f.endswith(".json")
            )
        except OSError:
            return []

    def load(self, name: str) -> Dict:
        """加载模板 workflow JSON。

        Args:
            name: 模板名称

        Returns:
            workflow dict

        Raises:
            FileNotFoundError: 模板不存在
        """
        path = self._path_for(name)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Workflow 模板不存在: {name}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, name: str, workflow: Dict) -> str:
        """保存 workflow 到模板文件。

        Args:
            name: 模板名称
            workflow: workflow JSON dict

        Returns:
            保存的文件路径
        """
        path = self._path_for(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(workflow, f, ensure_ascii=False, indent=2)
        logger.info(f"Workflow saved: {name} -> {path}")
        return path

    def delete(self, name: str) -> bool:
        """删除模板文件。

        Args:
            name: 模板名称

        Returns:
            True 如果删除成功，False 如果不存在
        """
        path = self._path_for(name)
        if os.path.isfile(path):
            os.remove(path)
            logger.info(f"Workflow deleted: {name}")
            return True
        return False

    def exists(self, name: str) -> bool:
        """检查模板是否存在"""
        return os.path.isfile(self._path_for(name))
