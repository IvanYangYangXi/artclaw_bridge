# 贡献指南 — ArtClaw Skills

感谢你为 ArtClaw 贡献 Skill！本文档说明如何提交、审核和发布 Skill。

## 提交流程

### 1. 准备 Skill

确保你的 Skill 包含以下文件：

```
my_skill/
├── SKILL.md            # ✅ 推荐 - AI 文档 + OpenClaw/ClawHub 分发
├── manifest.json       # ✅ 推荐 - MCP 注册元数据
├── __init__.py         # ✅ 必需 - 入口代码
└── references/         # 可选 - 参考文档
```

> `SKILL.md` 和 `manifest.json` 至少有一个。推荐两个都有。
> 详见 [MANIFEST_SPEC.md](MANIFEST_SPEC.md) 双文件策略。

### 2. 自查清单

提交前请确认：

- [ ] `manifest.json` 符合 [MANIFEST_SPEC.md](MANIFEST_SPEC.md) 规范（如有）
- [ ] `SKILL.md` frontmatter 包含 `name` + `description`（如有）
- [ ] `name` 使用 snake_case（manifest）或 kebab-case（SKILL.md），不超过 64 字符
- [ ] `category` 使用标准分类枚举（参见 `skills/categories.py`）
- [ ] `risk_level` 正确评估
- [ ] `software_version` 填写了测试过的版本范围
- [ ] 所有 `@ue_tool` 都有清晰的 `description`
- [ ] 错误处理完善，返回标准 JSON 格式
- [ ] 在 UE 外部 `import` 不会报错（`try: import unreal`）
- [ ] SKILL.md 包含工具说明、参数和使用流程
- [ ] 无硬编码路径，使用参数传入

### 3. 测试

```bash
# 本地验证（不执行 UE 操作）
artclaw skill test my_skill --dry-run

# UE 环境内测试
artclaw skill test my_skill --software unreal_engine
```

### 4. 提交 PR

#### 分支命名

```
skill/<category>/<skill-name>
```

例如：`skill/material/generate_pbr_textures`

#### PR 模板

```markdown
## Skill 信息

- **名称**: `my_skill`
- **分类**: material
- **风险级别**: low
- **适用软件**: unreal_engine 5.4+

## 功能描述

一段话描述此 Skill 的功能和使用场景。

## 测试

- [ ] UE 内手动测试通过
- [ ] dry-run 验证通过
- [ ] 错误场景测试（无效路径、空参数等）

## 截图/录屏（可选）

如有 UI 相关操作，附上截图。
```

## 代码审核标准

### 必须通过

1. **元数据完整**: manifest.json 或 SKILL.md 正确填写
2. **错误处理**: 所有异常都被捕获，返回标准错误格式
3. **安全性**: `risk_level` 与实际操作匹配
4. **兼容性**: `try: import unreal` 模式，UE 外不报错
5. **返回格式**: 标准 JSON，包含 `success` 字段

### 推荐通过

1. **文档**: SKILL.md 包含完整的工具说明和使用流程
2. **双文件**: 同时有 SKILL.md + manifest.json
3. **日志**: 关键操作有日志输出
4. **撤销**: 修改操作使用 `ScopedEditorTransaction`

### 禁止项

- ❌ 硬编码文件路径
- ❌ 无错误处理的 `unreal` API 调用
- ❌ 直接 `print()` 输出（使用 `unreal.log()`）
- ❌ `risk_level` 标低（实际操作风险高）
- ❌ 未声明的依赖

## 目录放置规则

Skill 统一放在 UE 插件运行时目录中：

| 层级 | 目录 | 说明 |
|------|------|------|
| 官方 | `Skills/00_official/<skill_name>/` | ArtClaw 官方维护 |
| 团队 | `Skills/01_team/<skill_name>/` | 团队共享定制 |
| 用户 | `Skills/02_user/<skill_name>/` | 个人私有 |
| 临时 | `Skills/99_custom/<skill_name>/` | 临时实验 |

> 提交到官方库的 PR 应放在 `00_official/` 层级。

## 版本规范

遵循 [语义化版本](https://semver.org/)：

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的新功能
- **PATCH**: 向后兼容的 bug 修复

## 问题和讨论

- 功能建议：创建 Issue，标签 `skill-request`
- Bug 报告：创建 Issue，标签 `skill-bug`
- 一般讨论：使用 Discussions

## 许可证

提交到官方库的 Skill 默认使用 MIT 许可证。如需使用其他许可证，请在 PR 中说明。
