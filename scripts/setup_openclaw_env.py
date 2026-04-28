#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — OpenClaw 环境自动安装脚本
=============================================

一键检测并安装 OpenClaw 运行环境，包括：
1. Node.js 检测（未安装则引导 / 自动下载安装）
2. OpenClaw 安装（npm install -g openclaw）
3. 跳过交互式初始化，直接写入最小配置
4. 注入 MCP Server 配置
5. 启动 Gateway
6. 引导用户配置 AI 模型 API Key（唯一需要手动的步骤）

如果用户选择了 ArtClaw 不支持的平台，也会引导安装 OpenClaw。

用法:
    python scripts/setup_openclaw_env.py
    python scripts/setup_openclaw_env.py --skip-gateway    # 不自动启动 Gateway
    python scripts/setup_openclaw_env.py --model deepseek  # 预设模型提供商
    python scripts/setup_openclaw_env.py --api-key sk-xxx  # 直接传入 API Key

由 install.bat / install.py 在用户选择 openclaw 平台时自动调用。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

# OpenClaw 配置目录
OPENCLAW_HOME = Path(os.path.expanduser("~/.openclaw"))
OPENCLAW_CONFIG = OPENCLAW_HOME / "openclaw.json"

# Node.js 最低版本
MIN_NODE_VERSION = (18, 0, 0)

# 支持的模型提供商预设
MODEL_PROVIDERS = {
    "openrouter": {
        "display_name": "OpenRouter (多模型聚合, 部分免费模型)",
        "env_key": "OPENROUTER_API_KEY",
        "default_model": "anthropic/claude-sonnet-4-20250514",
        "base_url": "https://openrouter.ai/api/v1",
        "register_url": "https://openrouter.ai/keys",
        "note": "Google 一键注册，部分模型免费，付费模型按量计费",
    },
    "aliyun": {
        "display_name": "阿里云百炼 (每模型送 100 万 tokens)",
        "env_key": "DASHSCOPE_API_KEY",
        "default_model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "register_url": "https://bailian.console.aliyun.com/",
        "free_tier": True,
        "note": "实名后每个模型独立送 100 万 tokens，90 天有效，模型最全",
    },
    "zhipu": {
        "display_name": "智谱AI (注册送 2000 万 tokens)",
        "env_key": "ZHIPU_API_KEY",
        "default_model": "glm-4-flash",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "register_url": "https://open.bigmodel.cn/",
        "free_tier": True,
        "note": "注册送 2000 万 tokens，含 GLM-4/GLM-5，3 个月有效",
    },
    "siliconflow": {
        "display_name": "硅基流动 (实名送 16 元, 模型多速度快)",
        "env_key": "SILICONFLOW_API_KEY",
        "default_model": "deepseek-ai/DeepSeek-V3",
        "base_url": "https://api.siliconflow.cn/v1",
        "register_url": "https://cloud.siliconflow.cn/",
        "free_tier": True,
        "note": "实名送 16 元通用券，180 天有效，支持 DeepSeek/Qwen/GLM/Kimi",
    },
    "anthropic": {
        "display_name": "Anthropic (Claude, 效果最好)",
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
        "register_url": "https://console.anthropic.com/",
        "note": "付费，效果最好，推荐长期使用",
    },
    "openai": {
        "display_name": "OpenAI (GPT)",
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "register_url": "https://platform.openai.com/api-keys",
        "note": "付费，通用选择",
    },
}

# ArtClaw 支持的平台列表
SUPPORTED_PLATFORMS = ["openclaw", "lobster"]

# 不支持的平台（引导用 OpenClaw 替代）
UNSUPPORTED_PLATFORM_MSG = """
  ╔══════════════════════════════════════════════════════════════╗
  ║  该平台暂不支持作为 ArtClaw Bridge 的 Agent 后端。           ║
  ║                                                              ║
  ║  推荐使用 OpenClaw — 开源、免费、功能完整：                   ║
  ║    - 多模型支持 (Claude/GPT/DeepSeek/本地模型)               ║
  ║    - 完整的 Agent 能力 (记忆/Skill/Cron/多会话)             ║
  ║    - MCP 原生支持 (与 ArtClaw Bridge 无缝对接)              ║
  ║                                                              ║
  ║  是否安装 OpenClaw 作为 Agent 平台？                         ║
  ╚══════════════════════════════════════════════════════════════╝
"""


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def cprint(tag: str, msg: str, color: str = "white"):
    """带颜色的标签打印"""
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "cyan": "\033[96m",
        "white": "\033[0m",
        "bold": "\033[1m",
    }
    reset = "\033[0m"
    c = colors.get(color, "")
    print(f"{c}[{tag}]{reset} {msg}")


def run_cmd(cmd: list[str], check: bool = True, capture: bool = False,
            timeout: int = 120) -> subprocess.CompletedProcess | None:
    """运行命令，统一错误处理"""
    try:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None
    except subprocess.CalledProcessError as e:
        if capture:
            return e
        return None
    except subprocess.TimeoutExpired:
        cprint("超时", f"命令执行超时 ({timeout}s): {' '.join(cmd)}", "yellow")
        return None


def parse_version(version_str: str) -> tuple[int, ...]:
    """解析版本字符串为元组 'v18.20.1' -> (18, 20, 1)"""
    import re
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_str)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


# ---------------------------------------------------------------------------
# 步骤 1: 检测 Node.js
# ---------------------------------------------------------------------------

def check_nodejs() -> bool:
    """检测 Node.js 是否可用且版本满足要求"""
    node_path = shutil.which("node")
    if not node_path:
        return False

    result = run_cmd(["node", "--version"], capture=True, check=False)
    if not result or result.returncode != 0:
        return False

    version = parse_version(result.stdout.strip())
    if version < MIN_NODE_VERSION:
        cprint("警告", f"Node.js 版本过低: v{'.'.join(map(str, version))}，需要 >= v{'.'.join(map(str, MIN_NODE_VERSION))}", "yellow")
        return False

    cprint("OK", f"Node.js v{'.'.join(map(str, version))} ({node_path})", "green")
    return True


def install_nodejs() -> bool:
    """引导或自动安装 Node.js"""
    print()
    cprint("需要", "Node.js >= v18 (OpenClaw 运行时依赖)", "yellow")
    print()

    system = platform.system()

    if system == "Windows":
        # Windows: 尝试 winget 安装
        winget = shutil.which("winget")
        if winget:
            print("  检测到 winget，正在自动安装 Node.js LTS...")
            result = run_cmd(
                ["winget", "install", "OpenJS.NodeJS.LTS",
                 "--accept-package-agreements", "--accept-source-agreements"],
                check=False, timeout=300,
            )
            if result and result.returncode == 0:
                cprint("OK", "Node.js 安装完成（可能需要重新打开终端）", "green")
                # 刷新 PATH
                _refresh_path_windows()
                return check_nodejs()

        # winget 失败或不存在，引导手动安装
        print()
        print("  ┌─────────────────────────────────────────────────┐")
        print("  │  请手动安装 Node.js:                             │")
        print("  │                                                  │")
        print("  │  下载地址: https://nodejs.org/                   │")
        print("  │  推荐版本: LTS (v20+)                           │")
        print("  │                                                  │")
        print("  │  安装完成后重新运行此脚本即可。                   │")
        print("  └─────────────────────────────────────────────────┘")
        print()
        return False

    elif system == "Darwin":
        # macOS: 尝试 brew
        brew = shutil.which("brew")
        if brew:
            print("  检测到 Homebrew，正在安装 Node.js...")
            result = run_cmd(["brew", "install", "node"], check=False, timeout=300)
            if result and result.returncode == 0:
                return check_nodejs()

        print("  请运行: brew install node 或访问 https://nodejs.org/")
        return False

    else:
        # Linux
        print("  请使用包管理器安装 Node.js >= 18:")
        print("    Ubuntu/Debian: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs")
        print("    Arch: sudo pacman -S nodejs npm")
        print("    或访问: https://nodejs.org/")
        return False


def _refresh_path_windows():
    """尝试刷新 Windows PATH（winget 安装后 PATH 不会立即生效）"""
    # 从注册表重新读取 PATH
    try:
        import winreg
        env_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )
        sys_path, _ = winreg.QueryValueEx(env_key, "Path")
        winreg.CloseKey(env_key)

        user_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        try:
            user_path, _ = winreg.QueryValueEx(user_key, "Path")
        except FileNotFoundError:
            user_path = ""
        winreg.CloseKey(user_key)

        os.environ["PATH"] = f"{user_path};{sys_path}"
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 步骤 2: 检测/安装 OpenClaw
# ---------------------------------------------------------------------------

def check_openclaw() -> bool:
    """检测 OpenClaw 是否已安装"""
    openclaw_path = shutil.which("openclaw")
    if not openclaw_path:
        return False

    result = run_cmd(["openclaw", "--version"], capture=True, check=False)
    if result and result.returncode == 0:
        version = result.stdout.strip()
        cprint("OK", f"OpenClaw {version} ({openclaw_path})", "green")
        return True
    return False


def install_openclaw_package() -> bool:
    """通过 npm 全局安装 OpenClaw"""
    cprint("安装", "正在安装 OpenClaw (npm install -g openclaw)...", "cyan")
    print()

    result = run_cmd(
        ["npm", "install", "-g", "openclaw"],
        check=False,
        timeout=120,
    )

    if result and result.returncode == 0:
        cprint("OK", "OpenClaw 安装完成!", "green")
        return check_openclaw()
    else:
        cprint("错误", "OpenClaw 安装失败", "red")
        print("  请手动运行: npm install -g openclaw")
        print("  如果权限不足，尝试: npm install -g openclaw --prefix ~/.npm-global")
        return False


# ---------------------------------------------------------------------------
# 步骤 3: 写入最小配置（跳过交互式初始化）
# ---------------------------------------------------------------------------

def write_minimal_config(provider: str | None = None, api_key: str | None = None,
                         model: str | None = None):
    """
    写入最小可用的 OpenClaw 配置，跳过所有交互式设置。
    只保留 AI 运行必需的字段。

    OpenClaw 模型配置格式 (openclaw.json):
      models.providers.<name> = {
        baseUrl: "https://...",
        apiKey: "sk-...",
        api: "openai-completions",    # 所有 OpenAI 兼容都用这个
        models: [{ id: "model-id", name: "显示名" }]
      }
      models.default = "<provider>/<model-id>"
    """
    OPENCLAW_HOME.mkdir(parents=True, exist_ok=True)

    # 读取现有配置（如有）
    config = {}
    if OPENCLAW_CONFIG.exists():
        try:
            config = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 如果已有完整配置（含 provider），不覆盖
    existing_providers = config.get("models", {}).get("providers", {})
    if existing_providers and config.get("plugins"):
        cprint("跳过", "OpenClaw 配置已存在，不覆盖", "yellow")
        return

    # 构建最小配置
    if "gateway" not in config:
        config["gateway"] = {}

    # 自动生成 auth token
    if "auth" not in config.get("gateway", {}):
        import secrets
        config["gateway"]["auth"] = {
            "token": secrets.token_hex(24),
        }

    # 模型配置
    if provider and api_key:
        provider_info = MODEL_PROVIDERS.get(provider, {})
        model_id = model or provider_info.get("default_model", "")
        display_name = provider_info.get("display_name", provider)

        if "models" not in config:
            config["models"] = {}

        # 设置默认模型: <provider>/<model-id>
        config["models"]["default"] = f"{provider}/{model_id}"
        config["models"]["mode"] = "merge"

        # 注册 provider（OpenAI 兼容格式）
        if "providers" not in config["models"]:
            config["models"]["providers"] = {}

        prov_entry = {
            "apiKey": api_key,
            "api": "openai-completions",
            "models": [
                {"id": model_id, "name": display_name.split("(")[0].strip()},
            ],
        }

        # base_url: Anthropic/OpenAI 原生不需要，第三方 OpenAI 兼容的需要
        base_url = provider_info.get("base_url")
        if base_url:
            prov_entry["baseUrl"] = base_url

        config["models"]["providers"][provider] = prov_entry

        cprint("模型", f"默认模型: {provider}/{model_id}", "cyan")
        if base_url:
            cprint("模型", f"API 地址: {base_url}", "cyan")

    # 确保 plugins 结构存在
    if "plugins" not in config:
        config["plugins"] = {"allow": [], "entries": {}}

    # 写入
    OPENCLAW_CONFIG.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    cprint("OK", f"OpenClaw 配置已写入: {OPENCLAW_CONFIG}", "green")


# ---------------------------------------------------------------------------
# 步骤 4: 注入 MCP 配置
# ---------------------------------------------------------------------------

def inject_mcp_config(dccs: list[str] | None = None):
    """调用已有的 setup_openclaw_config.py 注入 MCP Server 配置"""
    config_script = ROOT_DIR / "platforms" / "openclaw" / "setup_openclaw_config.py"

    if not config_script.exists():
        cprint("警告", "setup_openclaw_config.py 不存在，跳过 MCP 配置", "yellow")
        return

    # 构建参数
    args = [sys.executable, str(config_script)]
    if dccs:
        for dcc in dccs:
            args.append(f"--{dcc}")
    else:
        # 默认注入所有常用 DCC
        args.extend(["--ue", "--maya", "--max", "--blender", "--sd", "--sp", "--comfyui"])

    cprint("配置", "注入 MCP Server 配置...", "cyan")
    result = run_cmd(args, check=False, timeout=30)
    if result and result.returncode == 0:
        cprint("OK", "MCP 配置注入完成", "green")
    else:
        cprint("警告", "MCP 配置注入失败，请稍后手动运行 setup_openclaw_config.py", "yellow")


# ---------------------------------------------------------------------------
# 步骤 5: 启动 Gateway
# ---------------------------------------------------------------------------

def start_gateway() -> bool:
    """启动 OpenClaw Gateway（如果未运行）"""
    # 检查 Gateway 状态
    result = run_cmd(["openclaw", "gateway", "status"], capture=True, check=False)
    if result and "running" in (result.stdout or "").lower():
        cprint("OK", "OpenClaw Gateway 已在运行", "green")
        return True

    cprint("启动", "正在启动 OpenClaw Gateway...", "cyan")
    result = run_cmd(["openclaw", "gateway", "start"], check=False, timeout=30)
    if result and result.returncode == 0:
        # 等待 Gateway 就绪
        time.sleep(2)
        cprint("OK", "OpenClaw Gateway 已启动", "green")
        return True
    else:
        cprint("警告", "Gateway 启动失败，请手动运行: openclaw gateway start", "yellow")
        return False


# ---------------------------------------------------------------------------
# 步骤 6: 引导配置 API Key
# ---------------------------------------------------------------------------

def prompt_api_key(provider: str | None = None) -> tuple[str, str] | None:
    """
    交互式引导用户选择模型提供商并输入 API Key。
    返回 (provider, api_key) 或 None（跳过）。
    """
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║         配置 AI 模型 (最后一步!)                      ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  OpenClaw 需要一个 AI 模型 API Key 才能工作。")
    print("  支持的提供商:")
    print()
    print("    [1] OpenRouter             — ⭐ 推荐! 部分模型免费，Google 一键注册")
    print("    [2] 阿里云百炼              — 🆓 每模型送 100 万 tokens，模型最全")
    print("    [3] 智谱AI                  — 🆓 注册送 2000 万 tokens")
    print("    [4] 硅基流动                — 🆓 实名送 16 元，模型多速度快")
    print("    [5] Anthropic (Claude)      — 效果最好 (付费)")
    print("    [6] OpenAI (GPT)            — 通用选择 (付费)")
    print("    [S] 跳过 (稍后手动配置)      — openclaw configure")
    print()

    if provider and provider in MODEL_PROVIDERS:
        choice_map = {"openrouter": "1", "aliyun": "2", "zhipu": "3",
                      "siliconflow": "4", "anthropic": "5", "openai": "6"}
        choice = choice_map.get(provider, "")
    else:
        choice = input("  请选择 [1/2/3/4/5/6/S]: ").strip()

    provider_keys = list(MODEL_PROVIDERS.keys())
    if choice in ("1", "2", "3", "4", "5", "6"):
        idx = int(choice) - 1
        selected_provider = provider_keys[idx]
    elif choice.upper() == "S" or choice == "":
        print()
        cprint("跳过", "稍后运行 'openclaw configure' 配置模型", "yellow")
        return None
    else:
        cprint("跳过", "无效选择，稍后运行 'openclaw configure' 配置", "yellow")
        return None

    prov_info = MODEL_PROVIDERS[selected_provider]
    print()
    print(f"  选择: {prov_info['display_name']}")

    # 显示将要配置的信息
    default_model = prov_info.get("default_model", "N/A")
    base_url = prov_info.get("base_url", "")
    print(f"  默认模型: {default_model}")
    if base_url:
        print(f"  API 地址: {base_url}")
    print(f"  协议格式: OpenAI 兼容 (openai-completions)")

    # 显示注册链接
    register_url = prov_info.get("register_url", "")
    if register_url:
        print()
        if prov_info.get("free_tier"):
            print(f"  🆓 该平台有免费额度! 注册获取 API Key:")
        else:
            print(f"  获取 API Key:")
        print(f"     {register_url}")

    # 显示备注
    note = prov_info.get("note", "")
    if note:
        print(f"  备注: {note}")

    print()

    # 检查环境变量是否已有
    env_val = os.environ.get(prov_info["env_key"], "")
    if env_val:
        cprint("OK", f"已从环境变量读取 {prov_info['env_key']}", "green")
        return (selected_provider, env_val)

    api_key = input(f"  请输入 API Key (或直接回车跳过): ").strip()
    if not api_key:
        cprint("跳过", "稍后运行 'openclaw configure' 配置", "yellow")
        return None

    # 可选: 自定义模型 ID
    custom_model = input(f"  模型 ID (回车使用默认 {default_model}): ").strip()
    if custom_model:
        # 临时修改 provider_info 中的默认模型（影响后续 write_minimal_config）
        MODEL_PROVIDERS[selected_provider]["default_model"] = custom_model
        cprint("模型", f"使用自定义模型: {custom_model}", "cyan")

    # 可选: 自定义 API Base URL
    if base_url:
        custom_url = input(f"  API 地址 (回车使用默认): ").strip()
        if custom_url:
            MODEL_PROVIDERS[selected_provider]["base_url"] = custom_url
            cprint("地址", f"使用自定义 API 地址: {custom_url}", "cyan")

    return (selected_provider, api_key)


# ---------------------------------------------------------------------------
# 不支持的平台处理
# ---------------------------------------------------------------------------

def handle_unsupported_platform(platform_name: str) -> bool:
    """
    当用户选择了不支持的平台时，引导安装 OpenClaw。
    返回 True 表示用户同意安装 OpenClaw。
    """
    print(UNSUPPORTED_PLATFORM_MSG)
    choice = input("  安装 OpenClaw? [Y/n]: ").strip().lower()
    if choice in ("", "y", "yes"):
        return True
    else:
        print()
        cprint("提示", "如需使用其他平台，可参考:", "yellow")
        print("    - Claude Code: MCP 工具桥接模式（仅工具调用，聊天在 Claude Code 终端）")
        print("    - Cursor: 类似 Claude Code 的 MCP 桥接")
        print("    - 自建 Gateway: 参考 docs/features/wuzuCat/wuzuCat集成方案.md")
        print()
        return False


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def setup_openclaw_env(
    skip_gateway: bool = False,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    dccs: list[str] | None = None,
    from_platform: str | None = None,
) -> bool:
    """
    OpenClaw 环境一键安装主流程。

    Args:
        skip_gateway: 不自动启动 Gateway
        provider: 预设模型提供商
        api_key: 预设 API Key
        model: 预设模型名称
        dccs: 要配置的 DCC 列表
        from_platform: 用户原始选择的平台（用于不支持平台的引导）

    Returns:
        True 安装成功, False 失败或用户取消
    """
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║       ArtClaw Bridge — OpenClaw 环境配置             ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    # 如果是从不支持的平台引导过来
    if from_platform and from_platform not in SUPPORTED_PLATFORMS:
        if not handle_unsupported_platform(from_platform):
            return False

    # ── Step 1: Node.js ──
    cprint("步骤 1/5", "检测 Node.js...", "cyan")
    if not check_nodejs():
        if not install_nodejs():
            print()
            cprint("失败", "Node.js 未安装，无法继续。请安装后重新运行。", "red")
            return False

    # ── Step 2: OpenClaw ──
    print()
    cprint("步骤 2/5", "检测 OpenClaw...", "cyan")
    if not check_openclaw():
        if not install_openclaw_package():
            return False

    # ── Step 3: 配置 ──
    print()
    cprint("步骤 3/5", "写入 OpenClaw 配置...", "cyan")

    # 如果没有预设 provider/key，进入交互式
    if not api_key:
        result = prompt_api_key(provider)
        if result:
            provider, api_key = result

    write_minimal_config(provider, api_key, model)

    # ── Step 4: MCP 配置 ──
    print()
    cprint("步骤 4/5", "配置 MCP Bridge...", "cyan")
    inject_mcp_config(dccs)

    # ── Step 5: 启动 Gateway ──
    print()
    cprint("步骤 5/5", "启动 Gateway...", "cyan")
    if skip_gateway:
        cprint("跳过", "Gateway 启动已跳过 (--skip-gateway)", "yellow")
    else:
        start_gateway()

    # ── 完成 ──
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║         ✅ OpenClaw 环境配置完成!                     ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    if not api_key:
        print("  ⚠️  尚未配置 AI 模型 API Key，请运行:")
        print("     openclaw configure")
        print()

    print("  OpenClaw 已就绪，DCC 插件连接后即可使用。")
    print()
    return True


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ArtClaw Bridge — OpenClaw 环境一键安装",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/setup_openclaw_env.py                       # 交互式安装
  python scripts/setup_openclaw_env.py --model deepseek      # 预选 DeepSeek
  python scripts/setup_openclaw_env.py --api-key sk-xxx      # 直接传入 key
  python scripts/setup_openclaw_env.py --skip-gateway        # 不启动 Gateway
  python scripts/setup_openclaw_env.py --from-platform cursor # 从不支持的平台引导
        """,
    )
    parser.add_argument("--skip-gateway", action="store_true",
                        help="不自动启动 OpenClaw Gateway")
    parser.add_argument("--provider", choices=list(MODEL_PROVIDERS.keys()),
                        help="预设模型提供商 (跳过选择): openrouter/aliyun/zhipu/siliconflow/anthropic/openai")
    parser.add_argument("--api-key",
                        help="直接传入 API Key (跳过输入)")
    parser.add_argument("--model",
                        help="自定义模型名称")
    parser.add_argument("--from-platform",
                        help="用户原始选择的平台 (用于不支持平台的引导)")

    # DCC 选择
    parser.add_argument("--ue", action="store_true", help="配置 UE MCP")
    parser.add_argument("--maya", action="store_true", help="配置 Maya MCP")
    parser.add_argument("--max", action="store_true", help="配置 Max MCP")
    parser.add_argument("--blender", action="store_true", help="配置 Blender MCP")
    parser.add_argument("--houdini", action="store_true", help="配置 Houdini MCP")
    parser.add_argument("--sp", action="store_true", help="配置 SP MCP")
    parser.add_argument("--sd", action="store_true", help="配置 SD MCP")
    parser.add_argument("--comfyui", action="store_true", help="配置 ComfyUI MCP")

    args = parser.parse_args()

    # 收集 DCC
    dccs = []
    for dcc in ["ue", "maya", "max", "blender", "houdini", "sp", "sd", "comfyui"]:
        if getattr(args, dcc, False):
            dccs.append(dcc)

    success = setup_openclaw_env(
        skip_gateway=args.skip_gateway,
        provider=args.provider,
        api_key=args.api_key,
        model=args.model,
        dccs=dccs or None,
        from_platform=args.from_platform,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
