"""
workflow_utils.py - ComfyUI Workflow 分析工具
===============================================

移植自 MeiGen-AI-Design-MCP 的 detectNodes / getWorkflowSummary / getEditableNodes。

功能:
  - detect_nodes(): 自动检测 workflow 中的关键节点（sampler/prompt/checkpoint 等）
  - get_workflow_summary(): 提取模型/步数/CFG/尺寸等摘要信息
  - get_editable_nodes(): 列出可编辑参数的人类可读文本
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("artclaw.comfyui.workflow_utils")

# ── 节点类型匹配规则（模糊匹配 class_type） ──

_NODE_PATTERNS = {
    "sampler": [
        "KSampler", "KSamplerAdvanced", "SamplerCustom",
        "KSamplerSelect", "SamplerDPMPP",
    ],
    "positive_prompt": [
        "CLIPTextEncode", "CLIPTextEncodeSDXL",
        "BNK_CLIPTextEncodeAdvanced",
    ],
    "negative_prompt": [
        "CLIPTextEncode", "CLIPTextEncodeSDXL",
        "BNK_CLIPTextEncodeAdvanced",
    ],
    "checkpoint": [
        "CheckpointLoaderSimple", "CheckpointLoader",
        "unCLIPCheckpointLoader",
    ],
    "load_image": [
        "LoadImage", "LoadImageMask",
    ],
    "save_image": [
        "SaveImage", "PreviewImage",
    ],
    "vae_decode": [
        "VAEDecode", "VAEDecodeTiled",
    ],
    "latent_image": [
        "EmptyLatentImage", "EmptySD3LatentImage",
    ],
    "lora": [
        "LoraLoader", "LoraLoaderModelOnly",
    ],
    "controlnet": [
        "ControlNetLoader", "ControlNetApply",
        "ControlNetApplyAdvanced",
    ],
}


def detect_nodes(workflow: Dict) -> Dict[str, List[Dict]]:
    """模糊匹配 class_type，检测 workflow 中的关键节点。

    Args:
        workflow: ComfyUI API 格式 workflow（key 为节点 ID）

    Returns:
        {
            "sampler": [{"node_id": "5", "class_type": "KSampler", "inputs": {...}}],
            "positive_prompt": [...],
            ...
        }
    """
    result: Dict[str, List[Dict]] = {k: [] for k in _NODE_PATTERNS}

    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            continue

        class_type = node_data.get("class_type", "")
        inputs = node_data.get("inputs", {})

        for role, patterns in _NODE_PATTERNS.items():
            if class_type in patterns:
                # 区分 positive/negative prompt：
                # 通过连接关系判断（连到 sampler 的 positive/negative 输入）
                entry = {
                    "node_id": node_id,
                    "class_type": class_type,
                    "inputs": inputs,
                }

                if role == "positive_prompt" or role == "negative_prompt":
                    # 同一个 CLIPTextEncode 可能同时匹配 positive 和 negative，
                    # 先统一放入 positive，后续通过 _resolve_prompt_roles 修正
                    if role == "positive_prompt":
                        result["positive_prompt"].append(entry)
                    # negative_prompt 暂不添加，等 _resolve 阶段处理
                else:
                    result[role].append(entry)
                break

    # 通过 sampler 连接关系区分 positive/negative prompt
    _resolve_prompt_roles(workflow, result)

    return result


def _resolve_prompt_roles(workflow: Dict, detected: Dict[str, List[Dict]]) -> None:
    """通过 sampler 节点的连接关系，区分 positive 和 negative prompt 节点。

    ComfyUI 中，KSampler 的 positive/negative 输入指向不同的 CLIPTextEncode。
    连接格式: ["node_id", output_index]
    """
    samplers = detected.get("sampler", [])
    all_prompts = list(detected.get("positive_prompt", []))

    if not samplers or not all_prompts:
        return

    positive_ids = set()
    negative_ids = set()

    for sampler in samplers:
        inputs = sampler.get("inputs", {})

        # positive 连接
        pos_ref = inputs.get("positive")
        if isinstance(pos_ref, list) and len(pos_ref) >= 1:
            positive_ids.add(str(pos_ref[0]))

        # negative 连接
        neg_ref = inputs.get("negative")
        if isinstance(neg_ref, list) and len(neg_ref) >= 1:
            negative_ids.add(str(neg_ref[0]))

    # 重新分配
    new_positive = []
    new_negative = []

    for prompt in all_prompts:
        nid = prompt["node_id"]
        if nid in negative_ids:
            new_negative.append(prompt)
        else:
            new_positive.append(prompt)

    detected["positive_prompt"] = new_positive
    detected["negative_prompt"] = new_negative


def get_workflow_summary(workflow: Dict) -> Dict[str, Any]:
    """从 workflow 中提取关键参数摘要。

    Returns:
        {
            "model": str,       # checkpoint 模型名
            "steps": int,       # 采样步数
            "cfg": float,       # CFG scale
            "sampler": str,     # 采样器名称
            "scheduler": str,   # 调度器名称
            "seed": int,        # 种子
            "width": int,       # 图片宽度
            "height": int,      # 图片高度
            "positive": str,    # 正向提示词
            "negative": str,    # 负向提示词
            "loras": list,      # LoRA 列表
        }
    """
    detected = detect_nodes(workflow)
    summary: Dict[str, Any] = {}

    # Checkpoint
    checkpoints = detected.get("checkpoint", [])
    if checkpoints:
        summary["model"] = checkpoints[0]["inputs"].get("ckpt_name", "unknown")

    # Sampler 参数
    samplers = detected.get("sampler", [])
    if samplers:
        s_inputs = samplers[0]["inputs"]
        summary["steps"] = s_inputs.get("steps")
        summary["cfg"] = s_inputs.get("cfg")
        summary["sampler"] = s_inputs.get("sampler_name")
        summary["scheduler"] = s_inputs.get("scheduler")
        summary["seed"] = s_inputs.get("seed")

    # 尺寸（从 EmptyLatentImage）
    latents = detected.get("latent_image", [])
    if latents:
        l_inputs = latents[0]["inputs"]
        summary["width"] = l_inputs.get("width")
        summary["height"] = l_inputs.get("height")

    # 提示词
    positives = detected.get("positive_prompt", [])
    if positives:
        summary["positive"] = positives[0]["inputs"].get("text", "")

    negatives = detected.get("negative_prompt", [])
    if negatives:
        summary["negative"] = negatives[0]["inputs"].get("text", "")

    # LoRA
    loras = detected.get("lora", [])
    if loras:
        summary["loras"] = [
            {
                "name": l["inputs"].get("lora_name", ""),
                "strength_model": l["inputs"].get("strength_model", 1.0),
                "strength_clip": l["inputs"].get("strength_clip", 1.0),
            }
            for l in loras
        ]

    return summary


def get_editable_nodes(workflow: Dict) -> str:
    """列出 workflow 中可编辑参数的人类可读文本。

    Agent 可以用此函数了解 workflow 的可调参数，
    然后直接修改 workflow dict 再提交。

    Returns:
        多行文本，每行一个可编辑参数
    """
    lines = []

    # 不展示的内部参数
    _SKIP_KEYS = {"control_after_generate"}

    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            continue

        class_type = node_data.get("class_type", "unknown")
        inputs = node_data.get("inputs", {})

        editable = {}
        for key, value in inputs.items():
            if key in _SKIP_KEYS:
                continue
            # 跳过连接引用（list 类型表示连到其他节点）
            if isinstance(value, list):
                continue
            editable[key] = value

        if editable:
            lines.append(f"[Node {node_id}] {class_type}:")
            for key, value in editable.items():
                # 截断过长文本
                val_str = str(value)
                if len(val_str) > 100:
                    val_str = val_str[:97] + "..."
                lines.append(f"  {key} = {val_str}")
            lines.append("")

    return "\n".join(lines) if lines else "（无可编辑参数）"
