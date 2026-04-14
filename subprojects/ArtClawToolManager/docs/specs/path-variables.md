# 路径变量参考（Path Variables Reference）

> 版本: 1.0
> 更新日期: 2026-04-14

---

## 概述

ArtClaw 触发规则的筛选条件（`filters.path`）支持 **路径变量**（`$variable`）前缀。引擎在运行时将变量解析为实际的绝对路径，避免在工具脚本和 manifest 中硬编码路径。

---

## 变量列表

| 变量 | 说明 | 解析来源 | 示例值（Windows） |
|------|------|----------|-------------------|
| `$project_root` | ArtClaw 项目源码根目录 | `~/.artclaw/config.json` → `project_root` 字段 | `D:\MyProject_D\artclaw_bridge` |
| `$tools_dir` | 用户工具安装目录 | 固定路径 `~/.artclaw/tools` | `C:\Users\xxx\.artclaw\tools` |
| `$skills_installed` | Skill 安装目录 | 固定路径 `~/.openclaw/skills` | `C:\Users\xxx\.openclaw\skills` |
| `$home` | 用户主目录 | 操作系统用户目录 | `C:\Users\xxx` |

### 变量与实际目录的对应关系

```
$project_root/tools/official/      ← 官方工具源码
$project_root/tools/marketplace/   ← 市集工具源码
$project_root/skills/              ← Skill 源码

$tools_dir/user/                   ← 用户自建工具（仅本地）

$skills_installed/                 ← 已安装的 Skill（所有来源）
```

---

## 使用方法

### 在 manifest.json 的 triggers 中

```json
{
  "triggers": [
    {
      "id": "on-change",
      "trigger": { "type": "watch", "events": ["created", "modified"] },
      "filters": {
        "path": [
          { "pattern": "$project_root/tools/**/*" },
          { "pattern": "$tools_dir/**/*" }
        ]
      }
    }
  ]
}
```

### 在 DCC 事件筛选中

```json
{
  "filters": {
    "path": [
      { "pattern": "/Game/Characters/**" },
      { "pattern": "/Game/Props/**", "exclude": true }
    ]
  }
}
```

> 不含 `$` 前缀的路径视为 DCC 内资源路径（如 UE 的 `/Game/...`、Maya 的场景路径），不做变量替换。

---

## 解析规则

1. **前缀匹配替换**：`$variable/rest/of/path` → 将 `$variable` 替换为绝对路径
2. **无 `$` 前缀**：视为 DCC 内资源路径，原样传递
3. **变量值为空**（如 `$project_root` 未配置）→ 跳过该条目，不报错
4. **路径分隔符**：manifest 中统一用 `/`，引擎自动转换为系统分隔符

---

## 配置文件位置

### `~/.artclaw/config.json`

```json
{
  "project_root": "D:/MyProject_D/artclaw_bridge",
  "disabled_skills": [],
  "pinned_skills": []
}
```

其中 `project_root` 是必须配置的字段——官方工具、市集工具、Skill 源码都从此目录加载。

---

## 常见用法示例

| 场景 | pattern | 说明 |
|------|---------|------|
| 监听所有源码工具变更 | `$project_root/tools/**/*` | official + marketplace |
| 监听用户工具变更 | `$tools_dir/**/*` | user 层 |
| 监听全部工具 | 同时写两条 path | 覆盖所有来源 |
| 监听已安装 Skill | `$skills_installed/**/*.md` | 只看 .md 文件变更 |
| 监听 Skill 源码 | `$project_root/skills/**/*` | 源码侧变更 |
| UE 资源路径 | `/Game/Characters/**` | DCC 内路径，不做变量替换 |
| 排除测试目录 | `$project_root/tools/**/test/**` + `exclude: true` | 排除模式 |

---

## 扩展变量

如果未来需要新增变量，在以下两处同步添加：

1. **后端引擎**：`filter_evaluator.py` → `PATH_VARIABLES` 字典
2. **工具脚本**：`_resolve_path_variables()` 函数（如合规检查器的 `main.py`）

变量命名规范：`$snake_case`，全小写，下划线分隔。
