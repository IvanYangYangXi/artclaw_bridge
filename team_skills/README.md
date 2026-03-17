# Team Skills 使用指南

## 概述

`team_skills/` 是团队共享的 Skill 库，通过 Git 版本控制在团队成员间同步。

## 目录结构

```
team_skills/
├── .gitignore          # Git 忽略规则
├── .gitkeep            # 保持目录存在
├── README.md           # 本文件
└── <skill_name>/       # 各 Skill 目录
    ├── manifest.json   # 元数据（必需）
    ├── __init__.py     # 入口代码（必需）
    └── README.md       # 使用说明（推荐）
```

## 工作流

### 添加 Skill 到团队库

```bash
# 方式 1: 用 CLI 直接创建到团队层
artclaw skill create my_tool --category scene --layer 01_team

# 方式 2: 从个人库发布到团队库
artclaw skill publish my_tool --target 01_team --message "v1.0: 初始版本"

# 方式 3: 手动复制
cp -r ~/.artclaw/skills/my_tool team_skills/
```

### Git 提交

```bash
cd artclaw/
git add team_skills/my_tool/
git commit -m "feat(skill): add my_tool - 批量重命名 Actor"
git push
```

### 团队成员获取

```bash
git pull
# Skill Hub 自动检测到新 Skill，热加载生效
```

## 冲突处理

### Skill 冲突类型

| 冲突类型 | 场景 | 处理方式 |
|----------|------|----------|
| 同名覆盖 | 官方库和团队库有同名 Skill | 官方库优先（优先级 0 > 1） |
| 版本冲突 | 两人同时修改同一 Skill | Git merge，人工审查 |
| 依赖冲突 | Skill A 依赖的 Skill B 被删除 | `artclaw skill check-deps` 检测 |

### Git Merge 冲突解决

当多人同时修改同一 Skill 时：

1. **manifest.json 冲突**: 以版本号较高的为准，手动合并其他字段
2. **__init__.py 冲突**: 按标准 Git 冲突解决流程，审查代码变更
3. **一般原则**: Skill 粒度小，尽量避免多人同时修改同一 Skill

### 冲突检测命令

```bash
# 检测当前所有层级的 Skill 冲突
artclaw skill list --all

# 查看冲突详情（CLI 会自动输出冲突信息）
artclaw skill info <name>
```

## 命名约定

- Skill 名称: `snake_case`，动词开头
- 团队前缀（可选）: `team_` 前缀避免与官方库冲突
- 提交消息: `feat(skill): add/update/remove <skill_name> - <简述>`

## 注意事项

- 不要提交 `__pycache__/` 和 `.pyc` 文件
- 不要提交个人测试数据
- 修改 Skill 后务必更新 `manifest.json` 中的 `version` 字段
- 重大变更请在 Skill 的 `README.md` 中记录
