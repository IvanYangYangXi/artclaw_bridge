# Phase 4.3: 版本管理 + 发布到市集

> 对应工作日: Day 8-9

---

## 1. 版本管理（Day 8）

### 1.1 版本号规范

语义化版本: `MAJOR.MINOR.PATCH`

### 1.2 版本存储

```
~/.artclaw/tools/user/batch-rename/
├── manifest.json              # 当前版本
├── main.py                    # 当前版本脚本
└── .versions/
    ├── v1.0.0/
    │   ├── manifest.json
    │   └── main.py
    └── v1.1.0/
        ├── manifest.json
        └── main.py
```

### 1.3 功能

| 功能 | API | 说明 |
|------|-----|------|
| 版本历史 | `GET /api/v1/tools/{id}/versions` | 列出所有版本 |
| 创建新版本 | `POST /api/v1/tools/{id}/versions` | 当前状态保存为新版本 |
| 版本回滚 | `POST /api/v1/tools/{id}/versions/{ver}/rollback` | 恢复到指定版本 |
| 版本对比 | `GET /api/v1/tools/{id}/versions/compare?v1=&v2=` | 对比两个版本差异 |

### 1.4 界面

版本管理入口在工具详情页中，显示版本列表，每个版本可查看/回滚/对比。

---

## 2. 发布到市集（Day 9）

### 2.1 发布流程

```
点击 [发布] → 填写发布表单 → 验证 → 确认 → 上传 → (审核) → 发布完成
```

### 2.2 发布表单

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 名称 | string | ✅ | 市集显示名称 |
| 简短描述 | string | ✅ | 一句话说明 |
| 详细描述 | text | ❌ | 功能特点、使用方法 |
| 分类 | enum | ✅ | 建模/材质/动画/导出/通用 |
| 标签 | string[] | ❌ | 搜索标签 |
| 预览图 | file | ❌ | 展示图片 |

### 2.3 发布状态

```
draft → pending_review → published
                       → rejected (附拒绝原因)
```

### 2.4 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/marketplace/publish` | POST | 发布工具 |
| `/api/v1/marketplace/{id}/status` | GET | 查看发布状态 |
| `/api/v1/marketplace/{id}/unpublish` | POST | 下架 |
| `/api/v1/marketplace/{id}/update` | PUT | 更新已发布版本 |

### 2.5 发布验证

发布前自动检查：
- [ ] 工具名称不为空
- [ ] manifest.json 格式正确
- [ ] 脚本文件存在且语法正确
- [ ] 无已知安全风险（禁止 os.system、eval 等）
- [ ] 依赖的 Skill 或工具存在

### 2.6 评分/评论（仅入口，后续开发）

本阶段只做 UI 入口预留，不实现后端逻辑：
- [ ] 工具详情页显示评分区域（占位，显示"即将推出"）
- [ ] 工具详情页显示评论区域（占位，显示"即将推出"）
- [ ] 卡片上显示评分占位（⭐ --）

实际评分/评论后端在 Phase 6（市集功能）中开发。
