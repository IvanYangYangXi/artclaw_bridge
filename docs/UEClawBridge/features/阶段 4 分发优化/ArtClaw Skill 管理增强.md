# ArtClaw Skill 管理 OpenClaw Skill 增强

> 版本: v1.0 | 日期: 2026-03-28 | 状态: 设计完成

## 问题描述

AI Agent 在 UE 对话中被要求"使用 ArtClaw 的 Skill 工具来处理 Skill 的修改和发布操作"时，不知道如何使用 ArtClaw 内置的 Skill 管理 API。Agent 转而去找 `openclaw skill publish` CLI 和 `clawhub` 工具，而非调用 `skill_sync.py` 提供的 Python API。

### 根因

1. `artclaw-skill-manage` SKILL.md 已有 Phase 4 的 `skill_sync` API 文档，但：
   - 内容在文件末尾，AI 可能因截断而看不到
   - 缺少关于 Skill 重命名、目录操作的指导
   - 缺少明确的"何时使用 ArtClaw Skill 管理而非 OpenClaw CLI"的判断指导

2. Agent 的 available_skills 中列出了 `artclaw-skill-manage`，但描述太简短，AI 未能识别它与"Skill 修改和发布"的关联

## 修复方案

### 更新 `~/.openclaw/skills/artclaw-skill-manage/SKILL.md`

1. **前置核心 API**: 将 `skill_sync` 的常用操作（安装/卸载/更新/同步/发布）提前到文档前半部分
2. **增加重命名流程**: 添加 Skill 重命名的完整步骤指南
3. **增加决策指南**: 明确"何时用 ArtClaw Skill 管理 vs OpenClaw CLI vs ClawHub"
4. **增加 OpenClaw SKILL.md 同步**: Skill 改名后如何同步更新 `~/.openclaw/skills/` 下的文档

### 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `~/.openclaw/skills/artclaw-skill-manage/SKILL.md` | 全面更新 |
| `skills/official/universal/artclaw-skill-manage/SKILL.md` (源码) | 同步更新 |

### 更新后的 SKILL.md 结构

```
# ArtClaw 技能管理
## 何时使用本 Skill
## Skill 生命周期操作
  ### 查看/列出 (skill_hub)
  ### 安装/卸载/同步 (skill_sync)
  ### 发布到市集 (skill_sync)
  ### 重命名 Skill
## Skill 创建
  ### 自动命名
  ### 代码生成
## Skill 包结构
## 命名规范
## 分层体系
## 常见操作速查表
```
