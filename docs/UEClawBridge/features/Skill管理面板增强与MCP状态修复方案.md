# Skill 管理面板增强与 MCP 状态修复方案

> 版本: v1.0
> 日期: 2026-03-30
> 关联文件: UEAgentSkillTab.cpp, UEAgentSkillTab_Data_impl.h, UEAgentSkillTab.h, UEAgentDashboard_StatusBar_impl.h, UEAgentLocalization.cpp

---

## 一、需求清单

| # | 需求 | 涉及文件 | 复杂度 |
|---|------|----------|--------|
| 1 | Skill 详情面板显示源路径+安装路径，两个打开按钮，版本不同时显示两个版本号 | SkillTab.cpp, _Data_impl.h, .h | 中 |
| 2 | Skill 管理面板增加"未安装"筛选按钮 + "软件分类"筛选行 | SkillTab.cpp, _Data_impl.h, Localization.cpp | 中 |
| 3 | 列表行作者不单独一行，和版本/层级等同行显示，减少行高 | SkillTab.cpp | 低 |
| 4 | 连接状态栏 MCP 始终显示 ✗ — 修复 MCP 就绪状态检测 | StatusBar_impl.h, mcp_server.py, openclaw_chat.py | 中 |
| 5 | 不属于 official/marketplace/user 的 Skill 统一归到"其他平台"分类 | _Data_impl.h, SkillTab.cpp | 低 |

---

## 二、设计方案

### 2.1 Skill 详情面板：源路径+安装路径+版本对比

**当前状态**: 详情面板只显示一个 `SourceDir`（路径），一个"打开所在目录"按钮。

**改动**:
- `FSkillEntry` 新增字段:
  - `InstalledDir` — 安装目录路径（运行时路径，`~/.openclaw/skills/{name}/`）
  - `SourceVersion` — 源码版本号（来自 `compare_source_vs_runtime` 的 updatable 信息）
  - 重命名 `SourcePath` → 删除此遗留字段（现在被误用来存 source_version）
- Python 脚本输出新增: `installed_dir`（安装目录）、`source_dir`（源码目录）语义分离
  - `source_dir` = 项目源码中的位置（`skills/official/unreal/{name}/`）
  - `installed_dir` = 安装运行时路径（`~/.openclaw/skills/{name}/`）
  - 对于 skill_hub 加载的 Skill，`source_dir` 就是运行时路径（已安装）
  - 对于平台目录扫描的 Skill，`installed_dir` = 已安装路径，`source_dir` = 项目源码路径（如果有）
- 详情面板:
  - 显示"源码路径"和"安装路径"两行
  - 如果两个版本不同，显示: `版本: v0.3.0 (源码: v0.4.0)`
  - 底部两个按钮: "打开源码目录" + "打开安装目录"（路径为空时禁用）

### 2.2 筛选增强：未安装 + 软件分类

**当前状态**: 只有层级筛选（全部/官方/市集/用户/其他平台）和搜索框。`InstallFilter` / `DccFilter` 变量已存在但 UI 上没有对应按钮。

**改动**:
- 层级筛选行末尾追加: `[未安装]` 按钮（InstallFilter="notinstalled"，橙色高亮）
  - 点击切换：选中 = 只显示未安装的，再点 = 恢复全部
  - 和层级筛选同一行，用分隔符或间距区分
- 新增一行"软件分类"筛选: `[全部] [UE] [Maya] [Max] [通用]`
  - DccFilter 值: "all" / "unreal" / "maya" / "max" / "universal"
  - 位于层级筛选行下方，单独一行
  - 蓝绿色调区分于层级筛选的蓝色
- 本地化新增:
  - `ManageFilterDcc` — "软件: " / "Software: "
  - `ManageFilterDccAll` — "全部" / "All"
  - `ManageFilterDccUE` — "UE" / "UE"
  - `ManageFilterDccMaya` — "Maya" / "Maya"
  - `ManageFilterDccMax` — "Max" / "Max"
  - `ManageFilterDccUniversal` — "通用" / "Universal"
  - `ManageFilterNotInstalled` — "未安装" / "Not Installed"

**排版**:
```
层级: [全部] [官方] [市集] [用户] [其他平台]  |  [未安装]
软件: [全部] [UE] [Maya] [Max] [通用]
[搜索框...                    ] 显示 12/35  [同步(3)]
────────────────────────────────────────────────
```

### 2.3 列表行作者同行显示

**当前状态**: Name+Version 一行，Name(ID) 第二行，Author 第三行 → 每行太高。

**改动**: 将 Author 放到 Name 右侧（与 Version 同行），用分隔符和不同颜色区分:
```
[*] [✓]  DisplayName  v0.3.0  · AuthorName    [official]  [运行时]   [...]
          skill_id_name
```
- Author 紧跟 Version，前面加 `·` 分隔，淡黄色
- 第二行只保留 skill ID name
- 移除 Author 的独立 SVerticalBox::Slot

### 2.4 MCP 状态修复

**根因分析**:
1. `_bridge_status.json` 是 C++ 轮询的唯一状态源
2. **只有 `mcp_server.py`** 调用 `write_bridge_status`（start 时 `mcp_ready=True`，stop 时 `mcp_ready=False`）
3. `openclaw_chat.py` (OpenClaw 桥接) **从不写** `_bridge_status.json`
4. 当 OpenClaw bridge 连接时，不会更新状态文件
5. `mcp_server.py` 写状态时设 `connected=True`，但这个 `connected` 被 C++ 误读为 OpenClaw bridge 连接状态

**实际问题**: `mcp_server._start_server()` 写的 `connected=True, mcp_ready=True` 被 `_bridge_status.json` 存储。但:
- 如果 MCP server 启动后 `_bridge_status.json` 被 `openclaw_chat` 的某个操作覆盖（如果有的话），或文件不存在
- 更可能: `mcp_server.py` 的 `import openclaw_ws` 在 `except Exception: pass` 中静默失败，导致根本没写文件

**修复方案**: 让 C++ 直接通过 Python API 查询 MCP 状态，不依赖 `_bridge_status.json`:
- 在 `BridgeStatusPoll` 中，`mcp_ready` 单独查询: 调 Python `mcp_server.get_server().is_running()` 或检查 `mcp_server.get_server()._running`
- `_bridge_status.json` 的 `connected` 字段改为由 `openclaw_chat.py` 写入（socket 探测结果）
- 但最简方案: C++ 直接调 Python 查 MCP 状态，不经过文件

**最终方案（最小改动）**: 
- C++ `BridgeStatusPoll` 中增加独立的 MCP 状态检测：通过 `RunPythonAndCapture` 调用 `mcp_server.get_server()._running` 获取真实状态
- 保留 `_bridge_status.json` 用于 OpenClaw bridge 连接状态
- 频率: 每次 BridgeStatusPoll（2秒）附带检测一次 MCP 状态，开销可忽略

### 2.5 非标准 Layer 统一归到"其他平台"

**当前状态**: Layer 分类有 official/marketplace/user/custom/platform/openclaw 等。筛选按钮有"其他平台"(platform)，但很多 Skill 的 layer 值是 "openclaw" 或其他值，不在任何筛选按钮覆盖范围内。

**改动**:
- Python 脚本: 将不属于 official/marketplace/user/custom 的 layer 统一归为 `platform`
- `ApplyFilters()`: 筛选 "platform" 时包含所有非标准 layer（platform/openclaw/custom 等非 official/marketplace/user）
- 详情面板和列表行: 显示原始 layer 值（如 openclaw），颜色统一用紫色

---

## 三、文件改动清单

| 文件 | 改动类型 | 改动内容 |
|------|----------|----------|
| `UEAgentSkillTab.h` | 修改 | FSkillEntry 新增 InstalledDir，删除 SourcePath 遗留 |
| `UEAgentSkillTab_Data_impl.h` | 修改 | Python 脚本增加 installed_dir 输出，layer 归一化，DCC 筛选 |
| `UEAgentSkillTab.cpp` | 修改 | 筛选 UI（未安装+DCC），列表行 Author 同行，详情面板双路径 |
| `UEAgentDashboard_StatusBar_impl.h` | 不改 | 仅读取 bCachedMcpReady，逻辑不变 |
| `UEAgentDashboard_Main_impl.h` | 修改 | BridgeStatusPoll 增加 Python 查询 MCP 状态 |
| `UEAgentLocalization.cpp` | 修改 | 新增 DCC 筛选 + 详情面板本地化条目 |
| `mcp_server.py` | 可选修改 | 清理无效的 write_bridge_status 调用（不影响功能） |

---

## 四、实施顺序

1. **需求 3** — 列表行 Author 同行（最简单，立即可见效果）
2. **需求 5** — Layer 归一化到"其他平台"（Python 脚本 + ApplyFilters）
3. **需求 2** — 筛选增强（未安装按钮 + DCC 筛选行）
4. **需求 1** — 详情面板双路径+版本对比
5. **需求 4** — MCP 状态修复

---

## 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-03-30 | v1.0 | 初始版本 |
