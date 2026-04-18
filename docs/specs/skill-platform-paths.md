# Skill Platform Paths — 规范文档

> **版本**: 1.0.0 | **状态**: Active | **更新**: 2026-04-13

## 概述

ArtClaw 支持多个 AI 平台（OpenClaw、LobsterAI、Claude 等），不同平台的 Skill 安装目录不同。  
所有需要读取或检查 Skill 目录的组件，**必须通过统一 API 获取路径，禁止硬编码**。

---

## 1. 核心 API

### `bridge_config.get_skills_installed_path() → str`

返回当前平台已安装 Skill 的根目录（绝对路径，已展开 `~`）。

路径解析优先级：
1. `~/.artclaw/config.json` → `skills.installed_path`（用户显式配置或平台切换时写入）  
2. `~/.artclaw/config.json` → `platform.type` → `_PLATFORM_DEFAULTS[type].skills_installed_path`  
3. 硬编码默认值 `~/.openclaw/skills`

### `bridge_config.get_skill_checker_dirs() → dict`

返回完整的多位置检查信息，包括：

| 字段 | 类型 | 说明 |
|------|------|------|
| `platform_type` | str | 当前平台（openclaw / lobster / ...） |
| `skills_installed_path` | str | 已安装 Skill 目录 |
| `project_root` | str | 项目源码根目录 |
| `dcc_install_dirs` | list | 各 DCC 安装副本信息（见下） |
| `core_module_copies` | list | 核心模块副本对（src → dst） |

`dcc_install_dirs` 每项结构：
```json
{
  "label": "Maya 2024",
  "dcc": "maya",
  "path": "/abs/path/to/DCCClawBridge",
  "install_path": "/abs/path/to/maya/scripts/DCCClawBridge"
}
```

`core_module_copies` 每项结构：
```json
{
  "label": "core/skill_sync.py → DCC/core/skill_sync.py",
  "src": "/abs/path/core/skill_sync.py",
  "dst": "/abs/path/DCCClawBridge/core/skill_sync.py"
}
```

---

## 2. 平台路径表

| 平台 | Skill 安装目录 | 配置文件 |
|------|---------------|---------|
| OpenClaw | `~/.openclaw/skills/` | `~/.openclaw/openclaw.json` |
| LobsterAI | `%APPDATA%/LobsterAI/SKILLs/` | `%APPDATA%/LobsterAI/openclaw/state/openclaw.json` |
| Claude Desktop | `~/.claude/skills/` | `~/.claude/config.json` |
| Claude Code | `~/.claude/skills/` | `~/.claude.json` |
| Cursor | `~/.cursor/skills/` | `~/.cursor/mcp.json` |
| WorkBuddy | `~/.workbuddy/skills/` | `~/.workbuddy/config.json` |

平台切换由 `bridge_config.switch_platform(platform_type)` 完成，会同步写入 `~/.artclaw/config.json`。

---

## 3. Skill 目录结构规范

### 已安装目录（运行时）
```
{skills_installed_path}/
  {skill-name}/          ← 扁平结构，无 layer/dcc 子目录
    SKILL.md
    manifest.json        ← 可选
    __init__.py          ← 可选
    references/          ← 可选
```

### 源码仓库（project_root）
```
skills/
  {layer}/               ← official / marketplace / user
    {dcc}/               ← universal / unreal / maya / max / blender / ...
      {skill-name}/
        SKILL.md
        manifest.json
```

**Source 分类权威链：**  
`源码仓库文件夹 layer` > `SKILL.md frontmatter source:` > `"user"`（保守默认，不推断）

---

## 4. Skill 变更检测规则（Hash 优先）

| 条件 | 状态 | UI 动作 |
|------|------|---------|
| Hash 完全相同 | `synced` | 无 |
| Hash 不同，source_ver > inst_ver | `source_newer` | 🔄 更新 |
| Hash 不同，inst_ver > source_ver | `installed_newer` | ⬆️ 发布 |
| Hash 不同，版本相同或均缺失 | `modified` | 📝 发布（本地有改动未提交） |
| 两侧 mtime 都更新 | `conflict` | ⚠️ 需手动处理 |
| 源码中不存在该 Skill | `no_source` | 无（用户自建） |

> **关键规则**：版本号只用于判断方向，不代表"是否有变更"。Hash 是唯一的变更判据。

---

## 5. 多位置检查范围

`skill-version-checker` 工具通过 `get_skill_checker_dirs()` 获取所有需要检查的目录，覆盖：

1. **Skill installed vs source repo**（A 类检查）  
   - 检测路径: `skills_installed_path` vs `project_root/skills/{layer}/{dcc}/`  

2. **核心模块副本同步**（B 类检查）  
   - `core/skill_sync.py` → `DCCClawBridge/core/` + `UEClawBridge/Content/Python/`  
   - `core/bridge_core.py`, `bridge_config.py`, `memory_core.py` 同理  

3. **DCC 安装副本同步**（C 类检查）  
   - `DCCClawBridge/` → Maya / 3ds Max / Blender / Houdini / SP / SD / ComfyUI 安装目录  
   - 由 `get_skill_checker_dirs()` 自动检测已安装的 DCC  

---

## 6. 调用规范

### Tool Manager（server 端）
```python
# core/config.py — skills_path 属性
# 动态读取，无需重启即可响应平台切换
@property
def skills_path(self) -> Path:
    if self.SKILLS_DIR:                     # 显式 env 覆盖
        return Path(os.path.expanduser(self.SKILLS_DIR))
    return Path(_resolve_skills_path())     # 读 ~/.artclaw/config.json
```

### skill-version-checker（Tool 工具）
```python
# 通过 bridge_config.get_skill_checker_dirs() 获取所有路径
# 不在工具内硬编码任何路径
checker_dirs = get_skill_checker_dirs()
installed_path = checker_dirs["skills_installed_path"]
```

### DCC 插件内（skill_sync.py）
```python
from bridge_config import get_skills_installed_path
installed_dir = get_skills_installed_path()
```

---

## 7. 新平台接入规范

在 `bridge_config._PLATFORM_DEFAULTS` 中添加一条记录：

```python
"new_platform": {
    "display_name": "New Platform",
    "gateway_url": "ws://127.0.0.1:PORT",  # empty string for MCP-only platforms
    "mcp_port": 8080,
    "visible": True,
    "skills_installed_path": "~/.new_platform/skills",
    "mcp_config_path": "~/.new_platform/config.json",
    "mcp_config_key": "mcpServers",
},
```

然后在 `platforms/new_platform/` 下创建适配器，`get_skill_checker_dirs()` 会自动使用新路径。  
**无需修改任何检查工具或 Tool Manager。**

---

## 8. 相关文件索引

| 文件 | 职责 |
|------|------|
| `core/bridge_config.py` | 唯一路径 API 实现（`get_skills_installed_path`, `get_skill_checker_dirs`, `switch_platform`） |
| `subprojects/DCCClawBridge/core/bridge_config.py` | DCC 副本（与 core/ 保持同步，verify_sync.py 检查） |
| `subprojects/UEDAgentProj/.../Python/bridge_config.py` | UE 副本（同上） |
| `subprojects/ArtClawToolManager/src/server/core/config.py` | Tool Manager 配置，`skills_path` 属性动态读取 |
| `~/.artclaw/tools/official/skill-version-checker/main.py` | 全量检查工具，调用 `get_skill_checker_dirs()` |
| `verify_sync.py` | 开发辅助，核心/平台模块副本 hash 校验（CLI 工具） |
