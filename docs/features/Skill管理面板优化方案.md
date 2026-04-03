# Skill 管理面板优化方案

> 版本: v1.0  
> 日期: 2026-04-04  
> 范围: DCC 端 (Maya/Max Qt) + UE 端 (Slate C++) + 共享核心 (skill_sync.py)  

---

## 一、现状问题汇总

### 1.1 DCC 端 (skill_tab.py)

| # | 问题 | 现象 | 根因 |
|---|------|------|------|
| D1 | 发布按钮藏在详情页 | 用户必须点 `···` → 详情弹窗 → 发布按钮，操作路径太深 | `_make_skill_row()` 没有直接放发布按钮 |
| D2 | 版本号不显示 | 列表行的版本只有部分 Skill 显示（有 manifest.json 的才有） | 很多纯 SKILL.md 的 Skill 没有 `version` 字段，`query_all_skills()` 也没从 SKILL.md frontmatter 提取 |
| D3 | 作者不显示 | 列表行没有作者信息 | `_make_skill_row()` 没渲染 `author` 字段；`query_all_skills()` 的 OC 目录扫描段也没从 SKILL.md frontmatter 提取 author |
| D4 | "全量更新 (10)" 数字偏大 | 显示 10 但列表没有 10 个要更新的 | `total_sync = updatable + not_installed`，10 个是 SOURCE_ONLY（未安装）的 Skill 被计入。用户以为"全量更新"只更新已装的，实际包含未安装的。措辞误导 |
| D5 | 更新/发布按钮缺乏智能识别 | 所有已安装 Skill 都能发布，但大部分没修改过；更新按钮只在 `updatable=True` 时出现但判定不够准确 | 缺少"本地是否有未发布修改"的检测 |

### 1.2 UE 端 (UEAgentSkillTab*.cpp/.h)

| # | 问题 | 现象 | 根因 |
|---|------|------|------|
| U1 | 发布后版本号不更新 | 点发布(Patch/Minor/Major)后列表里版本号没变 | `publish_skill()` 更新了 manifest.json 的 version，但 UE 端 Python 扫描脚本读取 version 的链路：①skill_hub manifest 缓存了旧值，②OC 目录扫描段直接 `'version': ''` |
| U2 | 发布按钮对所有已安装 Skill 都显示 | 不管有没有修改，都能点发布 | `GenerateRow` 的 `bIsInstalled` 是唯一条件 |
| U3 | 更新/发布智能识别不足 | 同 D5 | 同 D5 |
| U4 | "全量更新" 数字同 D4 | 同 D4 | 同 D4 |

### 1.3 共享核心 (skill_sync.py)

| # | 问题 | 根因 |
|---|------|------|
| S1 | `publish_skill()` 不更新运行时 manifest 版本到 skill_hub 缓存 | `_notify_skill_hub()` 只调用 `hub.scan_and_register()` 但 UE 的 `scan_and_register(metadata_only=True)` 可能不重载 manifest |
| S2 | `compare_source_vs_runtime()` 的 updatable 只检测"源码 > 运行时"方向 | 没有"运行时 > 源码"（即本地有未发布修改）的检测 |
| S3 | 大量 Skill 没有 manifest.json 也没有 version | 纯 SKILL.md 的 Skill content_hash 相同时 updatable 为空——正确，但没有 version 展示给用户 |

---

## 二、核心概念定义

### 2.1 四种 Skill 状态

```
┌─────────────────────────────────────────────────────────┐
│                    Skill 生命周期                         │
│                                                         │
│  源码仓库 (skills/)  ←──发布──  已安装 (~/.openclaw/skills/) │
│       │                              │                  │
│       └──────安装/更新──────→         │                  │
│                                      │                  │
│  状态判定:                                               │
│  1. NOT_INSTALLED: 源码有, 运行时无                       │
│  2. UP_TO_DATE:    两边一致（版本相同或hash相同）          │
│  3. UPDATABLE:     源码较新（版本高 或 hash不同）          │
│  4. MODIFIED:      运行时较新（运行时hash≠源码hash）       │
│                    → 需要发布                             │
│  5. ORPHANED:      运行时有, 源码无                       │
└─────────────────────────────────────────────────────────┘
```

**关键新增: `MODIFIED` 状态** — 表示用户在已安装目录做了修改但尚未发布回源码。这是发布按钮应该高亮的唯一场景。

### 2.2 版本号 vs Content Hash

| 情况 | 版本号 | Content Hash | 更新判定 | 发布判定 |
|------|--------|-------------|----------|----------|
| 有 manifest.json 且有 version | ✅ | 辅助 | 版本号比较（源码>运行时 → updatable） | hash 比较（运行时≠源码 → modified） |
| 无 manifest.json 或无 version | ❌ | 主要 | hash 比较（源码hash≠运行时hash → updatable） | hash 比较（运行时hash≠源码hash → modified） |

**注意**: "更新"和"发布"的判定方向相反：
- **更新** = 源码 → 运行时（源码更新时推到运行时）
- **发布** = 运行时 → 源码（运行时修改后推回源码）

### 2.3 按钮显示规则

| 按钮 | 条件 | 位置 |
|------|------|------|
| **安装** | `install_status == not_installed` | 列表行内 |
| **更新** | `updatable == True`（源码比运行时新） | 列表行内，高亮色 |
| **发布** | `modified == True`（运行时比源码新）且已安装 | 列表行内 |
| **卸载** | 已安装 + layer ∈ {user, custom, marketplace} | 列表行内 |
| **详情** | 所有 Skill | 列表行内 `···` 按钮 |

**"发布"按钮不再对所有已安装 Skill 显示** — 只对有未发布修改的 Skill 显示。用户仍可通过详情页手动触发发布（即使无修改）。

### 2.4 "全量更新"按钮语义

当前: `全量更新 (N)` 其中 N = updatable + not_installed。用户混淆。

**改为**: 拆分显示：
- 按钮文本: `全量更新 (U个更新, I个未装)` — 仅 U>0 或 I>0 时启用
- 或者更简洁: `同步 (U+I)` 并在 tooltip 里说明
- **推荐方案**: `全量更新 (U)` 只计 updatable，**不含** not_installed。未安装的由用户手动安装或另一个"全部安装"按钮处理。

理由: "更新"的用户心理预期是"把已有的刷新到最新"，而不是"帮我装我没要过的东西"。

---

## 三、改动清单

### 3.1 skill_sync.py (共享核心)

#### 3.1.1 新增 `compare_source_vs_runtime()` 的 `modified` 列表

```python
def compare_source_vs_runtime() -> dict:
    """
    返回新增 modified 字段:
    {
        "available": [...],    # 源码有，运行时无 (可安装)
        "installed": [...],    # 运行时已安装
        "updatable": [...],    # 源码比运行时新 (可更新)
        "modified": [...],     # 运行时比源码新 (可发布) ← 新增
        "orphaned": [...],     # 运行时有，源码无
    }
    """
```

**判定逻辑** (两边都有的 Skill):

```python
# 有版本号: 比较版本
if src_ver and rt_ver:
    if _version_gt(src_ver, rt_ver):  # 源码版本 > 运行时
        updatable.append(...)
    # 即使版本相同，也检查 hash 判断是否有未发布修改
    if src_hash != rt_hash:
        if not _version_gt(src_ver, rt_ver):  # 排除已在 updatable 中的
            modified.append(...)

# 无版本号: 纯 hash 比较
else:
    if src_hash != rt_hash:
        # 谁更新? 我们无法从 hash 判断方向
        # 策略: 同时加入 updatable 和 modified，由 UI 决定
        # 或者: 只加入 modified（用户手动选择更新或发布）
        modified.append(...)
```

**版本比较辅助函数**:

```python
def _version_gt(a: str, b: str) -> bool:
    """a > b? 用 tuple 比较"""
    def _parse(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except:
            return (0, 0, 0)
    return _parse(a) > _parse(b)
```

#### 3.1.2 `publish_skill()` 增强

发布后必须更新运行时的 manifest.json version，**并** 让 content hash 两边一致：

1. 递增 version → 写入运行时 manifest.json ✅ (已有)
2. 复制运行时 → 源码 ✅ (已有)
3. **新增**: 发布后重新同步源码 → 运行时（确保两边 hash 一致）
4. **新增**: `_notify_skill_hub()` 强制 `scan_and_register(force=True)` 刷新缓存

#### 3.1.3 version/author 从 SKILL.md frontmatter 提取

`_scan_runtime_skills()` 和 `_scan_source_skills()` 都应该读取 SKILL.md frontmatter 提取 version/author:

```python
def _add_skill_entry(skills, skill_dir, layer):
    # 现有: 从 manifest.json 读 version
    # 新增: 无 manifest.json 时从 SKILL.md frontmatter 读 version + author
    if not version and skill_md_exists:
        fm = _parse_frontmatter_light(skill_md_path)
        version = fm.get("version", "")
        author = fm.get("author", "") or _ac_meta(fm, "author", "")
```

新增轻量 frontmatter 解析函数（不依赖 skill_hub）:

```python
def _parse_frontmatter_light(skill_md_path: Path) -> dict:
    """轻量解析 SKILL.md YAML frontmatter，只提取顶层 key-value"""
    ...
```

### 3.2 DCC 端 (skill_tab*.py)

#### 3.2.1 skill_tab_data.py — 补充 version/author/modified 数据

- `query_all_skills()` 的 OC 目录扫描段补充从 SKILL.md frontmatter 提取 author 和 version
- 新增 `modified` 字段到返回数据（来自 `compare_source_vs_runtime().modified`）
- `skill_sync.compare_source_vs_runtime()` 返回的 modified list → 映射到 `s["modified"] = True`

#### 3.2.2 skill_tab.py — SkillEntry 新增字段 + 列表行改造

**SkillEntry 新增**:
```python
@dataclass
class SkillEntry:
    ...
    author: str = ""          # 已有但未显示
    modified: bool = False     # 新增: 有未发布修改
```

**列表行 (`_make_skill_row`) 改造**:

```
┌─────────────────────────────────────────────────────────────┐
│ ★ ☑ Display Name   v1.0.0  by Author   [官方]  [已安装]    │
│        skill-name description text...           [发布][···] │
└─────────────────────────────────────────────────────────────┘
```

变更:
1. **版本号**: 已有但很多 Skill 没数据 → 数据层补全
2. **作者**: top_row 中 version 后面追加 `by {author}`
3. **发布按钮**: 移到列表行，只在 `modified=True` 时显示（高亮蓝色）
4. **全量更新按钮**: 只计 updatable 数量，不含 not_installed

#### 3.2.3 skill_tab_detail.py — 保留详情页发布入口

详情页仍保留"发布到源码仓库"按钮，作为兜底入口（即使无修改也能手动发布）。

### 3.3 UE 端 (UEAgentSkillTab*.cpp/.h)

#### 3.3.1 FSkillEntry 新增字段

```cpp
struct FSkillEntry
{
    ...
    bool bModified = false;   // 新增: 运行时有未发布修改
};
```

#### 3.3.2 Python 扫描脚本新增 modified 检测

`SkillRefreshPyScript` (UEAgentSkillTab_Data_impl.h) 在 "Phase 4: 未安装" 段后新增:

```python
# 从 compare_source_vs_runtime 获取 modified 列表
modified_names = {_canonical(i['name']) for i in diff.get('modified', [])}
for s in skills:
    if s['name'] in modified_names:
        s['modified'] = True
```

#### 3.3.3 GenerateRow 改造

- **发布按钮**: 可见条件从 `bIsInstalled` 改为 `bIsInstalled && Item->bModified`
- **版本号**: 已有 ✅ (从 Python 数据读取)
- **作者**: 已有 ✅ (GenerateRow 已渲染 Author)
- **全量更新**: 只计 updatable，不含 not_installed

#### 3.3.4 发布后刷新缓存

`OnPublishClicked` 的 Python 代码新增:
```python
# 发布后强制刷新 skill_hub 缓存
hub = get_skill_hub()
if hub:
    hub.scan_and_register()
```

已有 `_notify_skill_hub()` 会做这个，但需要确保 `scan_and_register()` 重新读取 manifest.json（而非用缓存）。

---

## 四、数据流全链路

### 4.1 列表刷新

```
[DCC] SkillTab.refresh()
  → skill_tab_data.query_all_skills()
    → skill_hub.scan_and_register(metadata_only=True)
    → 遍历 hub._all_manifests (已安装+代码)
    → 遍历 OC 目录 (已安装+仅SKILL.md)
    → skill_sync.compare_source_vs_runtime()
      → _scan_source_skills()     → {name: {ver, hash, layer, dcc}}
      → _scan_runtime_skills()    → {name: {ver, hash}}
      → 对比得出 available / updatable / modified
    → 合并到 result[]，补充 updatable/modified flag
  → SkillTab._rebuild_list()

[UE] SUEAgentSkillTab::Refresh()
  → RefreshData()
    → RunPythonAndCapture(SkillRefreshPyScript)
      → (同上 Python 逻辑，只是嵌在 C++ TEXT 宏中)
    → ParseSkillList(JSON)
  → BuildContent() → GenerateRow() per item
```

### 4.2 发布流程

```
用户点击 [发布] (列表行 或 详情页)
  → show_publish_dialog(entry, ...)  [DCC]
  → OnPublishClicked(Item)           [UE]
    → 选择 层级 + DCC + changelog + bump
    → skill_sync.publish_skill(name, layer, bump, changelog, dcc)
      1. 读运行时 manifest，递增 version
      2. 写回运行时 manifest.json
      3. 复制运行时 → 源码 (skills/{layer}/{dcc}/{name}/)
      4. 清理旧位置
      5. 同步源码 → 运行时 (确保 hash 一致)  ← 新增
      6. git add skills/ + commit
      7. _notify_skill_hub() 强制重扫
    → refresh UI
```

### 4.3 更新流程

```
用户点击 [更新] (列表行) 或 [全量更新]
  → skill_sync.update_skill(name) / sync_all()
    → install_skill(name)  # 覆盖安装: 源码 → 运行时
    → _notify_skill_hub()
  → refresh UI
```

---

## 五、实现步骤 (按顺序)

### Step 1: skill_sync.py 改造 (共享核心)

1. 新增 `_parse_frontmatter_light()` — 轻量 YAML frontmatter 解析
2. `_scan_source_skills()` + `_scan_runtime_skills()` 补充 author 字段
3. `_add_skill_entry()` 补充从 SKILL.md 读取 version/author
4. 新增 `_version_gt()` 版本比较函数
5. `compare_source_vs_runtime()` 新增 `modified` 列表
6. `publish_skill()` 发布后重新同步确保 hash 一致
7. 同步 core/ → DCC copy + UE copy + Maya 安装目录

### Step 2: DCC 端改造

1. `skill_tab_data.py` — 映射 modified flag + 补充 version/author
2. `skill_tab.py` — SkillEntry 新增 modified 字段
3. `skill_tab.py._make_skill_row()`:
   - 作者显示
   - 发布按钮移到列表行（modified 时显示）
   - 全量更新按钮数字只计 updatable
4. `skill_tab_detail.py` — 保留详情页发布入口不变

### Step 3: UE 端改造

1. `UEAgentSkillTab.h` — FSkillEntry 新增 `bModified`
2. `UEAgentSkillTab_Data_impl.h` — Python 脚本补充 modified 检测 + author/version 补全
3. `UEAgentSkillTab.cpp GenerateRow()` — 发布按钮条件改为 `bModified`
4. `UEAgentSkillTab.cpp BuildContent()` — 全量更新数字只计 updatable
5. `ParseSkillList()` — 解析 `modified` 字段

### Step 4: 同步 + 验证

1. `verify_sync.py` 全量校验
2. Maya 热重载验证（scripts/ + zh_CN/scripts/）
3. UE 编译验证（需要在 UE 编辑器中测试）

---

## 六、验证清单

| 场景 | 预期行为 | 验证方式 |
|------|----------|----------|
| 纯 SKILL.md 的 Skill（无 manifest） | 列表显示版本为空或 `-`，作者从 frontmatter 读取 | 查看 `artclaw-knowledge` 等 |
| 有 manifest.json 的 Skill | 版本号正确显示，作者正确显示 | 查看 `ue57_material_node_edit` |
| 修改了已安装 Skill 文件后刷新 | 该 Skill 出现 [发布] 按钮 | 手动编辑 `~/.openclaw/skills/X/SKILL.md` |
| 未修改的已安装 Skill | 不出现 [发布] 按钮 | 大多数 Skill 应该无发布按钮 |
| 源码更新后（版本号高于运行时） | 出现 [更新] 按钮 | 手动改源码版本号 |
| 全量更新按钮 | 数字只计 updatable，不含 not_installed | 当前应为 0（全部同步了） |
| 点击发布 → Patch | 版本号递增，列表刷新后显示新版本 | 发布后立即观察 |
| 10 个 SOURCE_ONLY | 不计入全量更新数字 | 当前应显示 `全量更新 (0)` |

---

## 七、边界情况

1. **无 project_root**: `compare_source_vs_runtime()` 返回 error → modified/updatable 全空 → 按钮都不显示（降级为只读列表）
2. **运行时有，源码无 (ORPHANED)**: 不显示发布按钮（因为源码没有对应位置可比较）。详情页的发布按钮仍可用，选择 DCC 目录后创建新位置。
3. **hash 碰撞**: MD5 前 12 位碰撞概率极低（16^12 = 2.8×10^14），实用上可忽略。
4. **两边都没版本号 + hash 不同**: 无法判断方向 → 标记为 modified（假设运行时更新，因为用户更可能在运行时目录编辑）。
5. **publish_skill 创建了 manifest.json 但 SKILL.md 没有 version**: 正常，SKILL.md 的 version 是可选的。manifest.json 是版本号的唯一权威来源。
