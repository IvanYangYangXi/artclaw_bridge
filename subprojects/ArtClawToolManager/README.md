# ArtClaw Tool Manager

> 统一工具管理器 - 整合 Skill 管理、Workflow 模板库、工具管理器的独立项目

---

## 项目简介

ArtClaw Tool Manager 是一个独立的 Web 应用，为 ArtClaw Bridge 生态系统提供统一的管理入口。

### 核心功能

- **Skill 管理**: 浏览、安装、更新、发布 Skills
- **Workflow 模板库**: 发现、执行、管理 Workflow 模板
- **工具管理器**: 官方工具、用户工具、工具创建向导
- **跨 DCC 支持**: 统一管理 UE、Maya、ComfyUI、SD 等 DCC 的工具

---

## 快速开始

### 安装

```bash
cd subprojects/ArtClawToolManager
pip install -r requirements.txt
cd src/web && npm install
```

### 启动

```bash
# 启动后端服务
python -m src.server.main

# 启动前端（开发模式）
cd src/web && npm run dev

# 或打开桌面快捷方式
# 双击 ArtClawToolManager.lnk (Windows)
```

### 访问

- Web 界面: http://localhost:9876
- API 文档: http://localhost:9876/docs

---

## 项目结构

```
ArtClawToolManager/
├── docs/                          # 项目文档
│   └── specs/                     # 架构设计文档
│       ├── architecture-design.md
│       ├── data-models.md
│       ├── api-design.md
│       └── ui-design.md           # UI 设计规范（最新）
├── src/
│   ├── web/                       # Web 前端 (React)
│   │   ├── src/
│   │   │   ├── components/        # UI 组件
│   │   │   ├── pages/             # 页面
│   │   │   ├── stores/            # 状态管理
│   │   │   └── api/               # API 客户端
│   │   └── package.json
│   │
│   ├── server/                    # 后端服务 (FastAPI)
│   │   ├── api/                   # REST API
│   │   ├── services/              # 业务逻辑
│   │   ├── models/                # 数据模型
│   │   └── main.py
│   │
│   └── dcc-panels/                # DCC 内嵌面板
│       ├── ue/                    # UE Slate 面板
│       ├── maya/                  # Maya Qt 面板
│       └── comfyui/               # ComfyUI 扩展
│
├── ArtClawToolManager.lnk         # Windows 快捷方式
├── README.md                      # 本文件
└── requirements.txt               # Python 依赖
```

---

## 文档索引

### 架构设计
- [系统架构设计](docs/specs/architecture-design.md) - 整体架构设计
- [数据模型设计](docs/specs/data-models.md) - 统一数据模型
- [API 设计](docs/specs/api-design.md) - REST API 规范
- [UI 设计](docs/specs/ui-design.md) - 界面设计规范（最新 v1.1）

### 开发文档
- [开发指南](docs/development-guide.md) - 开发环境搭建
- [部署指南](docs/deployment-guide.md) - 部署说明

### 相关文档
- [统一工具管理器设计](../../docs/features/artclaw-unified-tool-manager.md) - 主项目设计文档

---

## 相关项目

- [ArtClaw Bridge](../../) - 主项目
- [DCCClawBridge](../DCCClawBridge/) - DCC 桥接
- [UEClawBridge](../UEDAgentProj/) - UE 插件
- [ComfyUIClawBridge](../ComfyUIClawBridge/) - ComfyUI 扩展

---

## 许可证

MIT License - 参见 [LICENSE](LICENSE)
