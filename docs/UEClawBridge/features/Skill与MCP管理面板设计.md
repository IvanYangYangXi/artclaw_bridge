# Skill 与 MCP 管理面板设计

**版本**: v2.0  
**日期**: 2026-03-31  
**状态**: Phase 1-5 全部完成

---

## 1. 核心概念

### 1.1 两种 Skill 能力

| | 可执行代码包 | AI 参考文档 |
|---|---|---|
| **标志文件** | `__init__.py` + `manifest.json` | `SKILL.md` |
| **运行方式** | `execute_skill("name", params)` 直接调用 | AI 读 SKILL.md → 生成代码 → `run_python` 执行 |
| **适用** | 复杂固定逻辑（材质节点操作几百行） | 简单灵活逻辑（查选中对象几行） |
| **可同时存在** | ☑ | ☑ |

### 1.2 两个位置与数据流

```
① 项目源码（Git 仓库，分发给其他用户）          ② 已安装目录（本地运行时，AI 实际使用）
   skills/official/unreal/ue57_material_node_edit/    ~/.openclaw/workspace/skills/ue57_material_node_edit/
                                                          ├── manifest.json
          ──── 更新(源码→已安装) ────>                    ├── __init__.py
          <─── 发布(已安装→源码) ────                     └── SKILL.md
```

- **编辑**: 修改已安装目录中的文件
- **发布**: `publish_skill()` — 已安装→源码 + 版本号递增 + git commit
- **更新**: `update_skill()` / `sync_all()` — 源码→已安装（覆盖安装）
- **变更检测**: 有版本号用版本对比，无版本号用文件内容 hash 对比

### 1.3 配置驱动

```json
// ~/.artclaw/config.json
{
  "project_root": "D:\\MyProject_D\\artclaw_bridge",
  "disabled_skills": [],
  "pinned_skills": [],
  "platform": { "type": "openclaw" },
  "skills": { "installed_path": "~/.openclaw/workspace/skills" },
  "mcp": { "config_path": "~/.openclaw/openclaw.json", "config_key": "mcp.servers" }
}
```

- `project_root` 在 install.bat 运行时自动写入
- 无 `project_root` 时：发布/更新功能不可用，只显示已安装的 Skill
- 路径通过 `skills.installed_path` 配置，不同平台有不同默认值

---

## 2. Skill 命名规范

### 2.1 格式

```
{dcc}{major_version}_{skill_name}    (snake_case, 代码包)
{dcc}{major_version}-{skill-name}    (kebab-case, 纯文档)
```

| 示例 | 说明 |
|------|------|
| `ue57_material_node_edit` | UE 5.7 材质节点操作 |
| `maya24_curve_tools` | Maya 2024 曲线工具 |
| `artclaw-memory` | 通用（无 DCC 前缀） |
| `ue57-artclaw-context` | UE 5.7 编辑器上下文查询 |

### 2.2 旧名兼容

`_NAME_ALIAS_MAP` 自动映射旧名到新名：

| 旧名 | 新名 |
|------|------|
| `ue54_material_node_edit` | `ue57_material_node_edit` |
| `artclaw_material` | `ue57_material_node_edit` |
| `artclaw-context` | `ue57-artclaw-context` |

---

## 3. Skill 生命周期

### 3.1 创建

```
用户请求创建 → AI 自动命名 (auto_name) → 生成代码+manifest+SKILL.md
→ 写入 ~/.openclaw/workspace/skills/{name}/ → skill_hub 热加载 → 立即可用
```

### 3.2 编辑

直接修改已安装目录中的文件。skill_hub 文件监控自动热重载。

### 3.3 发布（已安装 → 源码仓库）

```
管理面板 [发布...] → 选择层级(marketplace/official) + DCC目录 + 版本递增
→ 更新 manifest 版本号 → copytree 到源码 skills/{layer}/{dcc}/ → git commit
```

### 3.4 更新（源码 → 已安装）

- **单条更新**: 管理面板每行 [更新] 按钮
- **全量更新**: 顶部 [全量更新] 按钮（安装未安装的 + 更新有差异的）
- 变更检测: 版本号对比 + 无版本号时 MD5 hash 对比

### 3.5 重命名

```python
from skill_sync import rename_skill
rename_skill("old_name", "new_name")
# 自动更新: 安装目录 + manifest + SKILL.md frontmatter + 源码目录
```

---

## 4. 启用/禁用/钉选

| 状态 | 含义 | 对 AI 的影响 |
|------|------|-------------|
| **☑ 启用** | Skill 已注册，AI 可按需调用 | AI 通过 SKILL.md 匹配或 list_skills() 发现 |
| **☐ 禁用** | 对 AI 不可见 | AI 完全看不到 |
| **📌 钉选** | 启用 + 强制注入上下文 | AI 每轮对话都看到，优先使用（最多 5 个） |

钉选实现: `_build_pinned_skills_context()` 读取 config → 加载 SKILL.md → 注入到 AI 首条消息前缀。

---

## 5. 目录结构

### 5.1 项目源码

```
skills/
├── official/
│   ├── universal/          # 通用 Skill
│   │   ├── artclaw-knowledge/
│   │   ├── artclaw-memory/
│   │   └── artclaw-skill-manage/
│   ├── unreal/             # UE 专用
│   │   ├── ue57_material_node_edit/
│   │   ├── ue57_get_material_nodes/
│   │   ├── ue57_generate_material_documentation/
│   │   ├── ue57-artclaw-context/
│   │   └── ue57-artclaw-highlight/
│   ├── maya/
│   └── max/
├── marketplace/
│   ├── universal/
│   ├── unreal/ ...
└── templates/              # 开发模板（扫描时跳过）
```

DCC 子目录不硬编码，`_scan_source_skills` 递归扫描所有子目录，支持未来扩展 blender/houdini 等。

### 5.2 已安装目录

```
~/.openclaw/workspace/skills/         # 扁平结构
├── artclaw-knowledge/
├── ue57_material_node_edit/
├── ue57-artclaw-context/
└── ...
```

---

## 6. 管理面板 UI

### 6.1 布局

```
层级: [全部] [官方] [市集] [用户] [其他平台]  |  [未安装]
软件: [全部] [UE] [Maya] [Max] [通用]          (动态生成)
[搜索框...                    ] 显示 12/35  [全量更新(3)]
────────────────────────────────────────────────
[*] [✓]  DisplayName  v0.3.0  · Author    [official]  [已安装]  [更新] [发布] [...]
          skill_id_name
```

### 6.2 操作按钮（按状态显示）

| 状态 | 显示的按钮 |
|------|-----------|
| 未安装 | [安装] |
| 已安装 + 可更新 | [更新] [发布] [...] |
| 已安装 user/custom/marketplace | [卸载] [发布] [...] |
| 已安装 | [发布] [...] |

### 6.3 发布弹窗

选择目标层级 (marketplace/official) + DCC 软件 (universal/UE/Maya/Max) + 版本递增 (patch/minor/major) + 变更说明。

### 6.4 详情弹窗

显示完整信息 + 源码版本对比 + "打开安装目录" / "打开源码目录" 两个按钮。

---

## 7. MCP Tab

- 从 `~/.artclaw/config.json` 的 `mcp.config_path` + `mcp.config_key` 读取配置
- `TraverseJsonPath` 通用 dot-separated JSON 路径遍历
- 每个 Server 显示: 名称、类型、URL、连接状态（端口探测）
- 启用/禁用写回配置文件

---

## 8. 开发分期

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 目录重构 + 改名迁移 + 配置体系 | ✅ 完成 |
| 2 | 管理面板框架 + MCP Tab | ✅ 完成 |
| 3 | Skill Tab — 查看/启用/禁用/钉选 | ✅ 完成 |
| 4 | Skill Tab — 安装/更新/发布/全量更新 | ✅ 完成 |
| 5 | Skill 创建命名优化 | ✅ 完成 |

### 关键实现文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `UEAgentSkillTab.cpp` | ~450 | UI 布局 + 列表渲染 |
| `UEAgentSkillTab_Data_impl.h` | ~250 | Python 脚本 + 数据解析 |
| `UEAgentSkillTab_Actions_impl.h` | ~300 | 操作: 启用/禁用/钉选/安装/卸载/发布 |
| `UEAgentMcpTab.cpp` | ~500 | MCP Server 管理 |
| `skill_sync.py` | ~770 | Skill 安装/卸载/更新/发布/重命名 |
| `skill_hub.py` | ~1300 | Skill 热加载 + 统一管理中心 |

---

## 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-03-27 | v1.0 | 初始版本 |
| 2026-03-27 | v1.4 | Phase 1-5 全部完成 |
| 2026-03-31 | v2.0 | 全面更新: ue54→ue57迁移, 两位置模型, 递归扫描, hash变更检测, rename API, 合并增强方案 |
