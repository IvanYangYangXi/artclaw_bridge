# Team Memory

团队共享记忆库 — 从实际开发中提炼的高价值规则。

AI Agent 启动时自动加载这些文件，在 briefing 中注入给 AI。

## 文件说明

| 文件 | 内容 | 优先级 | 加载时机 |
|------|------|--------|----------|
| crash_rules.md | 崩溃/严重错误规则 | P0 | 每次 briefing |
| gotchas.md | 反直觉行为/API 陷阱 | P0 | 每次 briefing |
| conventions.md | 项目规范/命名约定 | P1 | 仅首条消息 |
| platform_differences.md | 跨 DCC/平台差异 | P1 | 仅首条消息 |

## 格式规范

- 每条规则独立一行，以 `- ` 开头
- 标注适用范围: `[UE]` `[Maya]` `[Max]` `[All]` `[Python]` `[Windows]`
- 每条规则 ≤100 字符（精简！）
- 禁止放原始日志、冗长描述
- 新增规则追加到文件末尾（减少 Git 冲突）

## 维护

- AI Agent 定期从个人记忆中提炼高价值规则，提交到此目录
- 人类可直接编辑（VSCode/记事本）
- 通过 Git 版本管理，多人协作
