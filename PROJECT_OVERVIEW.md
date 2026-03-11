# ArtClaw 项目概览

## 📋 项目简介

ArtClaw 是一个集成到 Unreal Engine 编辑器的 AI 助手插件，通过自然语言交互实现对 UE 编辑器的智能控制，实现 UE 引擎与 WorkBuddy/OpenClaw 的双向自然语言交互。

## 🎯 核心功能

### 1. UE → LLM
用户在 UE 编辑器中通过自然语言输入，调用 WorkBuddy/OpenClaw 的大模型能力，帮助解决 UE 开发中的问题。

### 2. LLM → UE
用户在 WorkBuddy/OpenClaw 中输入指令，通过插件调用 UE 的功能，实现自动化任务。

## 🏗️ 技术架构

### 系统组件
1. **WorkBuddy 服务器**: 提供 LLM 接入能力，支持 OpenAI GPT-4、Claude、通义千问、腾讯混元等
2. **UE 插件**: 三层架构设计
   - 通信层：WebSocket 连接管理
   - LLM 集成层：消息处理和协议适配
   - 任务执行层：UE 功能调用

### 技术栈
- **引擎**: Unreal Engine 5.3+
- **语言**: C++ 17/20 + Blueprint
- **UI框架**: Slate + UMG
- **网络**: HTTP/WebSocket
- **JSON**: RapidJSON/UE JSON Utilities
- **并发**: AsyncTask + TaskGraph

## 📁 项目结构

```
ArtClaw/
├── docs/                          # 文档目录
│   ├── README.md                  # 文档索引
│   ├── 团队协作规范.md           # 团队协作规范
│   ├── 开发路线图.md             # 开发计划
│   ├── 技术接口设计.md           # 通信接口设计
│   ├── UEAI助手架构设计.md       # 系统架构设计
│   └── UE插件开发环境配置.md     # 环境配置指南
├── UE_Plugin_Example/             # UE 插件示例
├── UE插件技术调研.md              # 技术调研文档
├── UE集成方案.md                  # 集成方案文档
├── README.md                      # 项目说明
└── PROJECT_OVERVIEW.md           # 项目概览（本文件）
```

## 👥 开发团队

| 角色 | 成员 | 职责 |
|------|------|------|
| 产品经理 | 柒 | 需求记录、任务跟踪、团队管理 |
| 产品策划 | 小策 | 需求分析和用户体验设计 |
| 系统程序员 | 系统程序员 | 负责 WorkBuddy 端开发 |
| UE 程序员 | UE 引擎程序员 | 负责 UE 插件开发 |
| 技术架构师 | 技术架构师 | 负责技术方案设计 |
| QA 工程师 | QA 测试工程师 | 负责测试验收 |

## 📅 开发计划

### 总体周期：12-15 周

#### Phase 1: 基础框架搭建（4 周）
- Week 1-2：环境配置与架构设计
- Week 3-4：通信协议实现

#### Phase 2: 核心功能开发（6 周）
- Week 5-7：WorkBuddy 端开发
- Week 8-10：UE 插件开发

#### Phase 3: 测试与优化（2 周）
- Week 11-12：集成测试与性能优化

#### Phase 4: 部署与文档（2-3 周）
- Week 13-15：最终验收与文档完善

## 🔧 开发环境

### 工程信息
- **工程目录**: `D:\MyProject\ArtClaw`
- **GitHub 仓库**: https://github.com/IvanYangYangXi/artclaw
- **Git 分支**: main (主分支)

### 环境要求
- **操作系统**: Windows 10/11 64位
- **UE版本**: Unreal Engine 5.3+
- **开发工具**: Visual Studio 2022
- **Git 版本控制**: 必需

## 📖 快速开始

### 1. 克隆仓库
```bash
git clone https://github.com/IvanYangYangXi/artclaw.git
cd artclaw
```

### 2. 阅读文档
1. 团队协作规范：`docs/团队协作规范.md`
2. 开发路线图：`docs/开发路线图.md`
3. 技术架构：`docs/UEAI助手架构设计.md`
4. 环境配置：`docs/UE插件开发环境配置.md`

### 3. 开始开发
```bash
# 切换到开发分支（如果存在）
git checkout develop

# 或创建新的功能分支
git checkout -b feature/your-feature-name

# 开始开发...
```

## 🤝 贡献指南

### 提交规范
每位成员完成各自任务后，需要及时提交代码：
- 提交信息使用英文，格式清晰
- 重要功能和 bug 修复需要创建 issue 和 PR
- 遵循 Git 工作流程和代码规范

### 详细规范
请参考：`docs/团队协作规范.md`

## 📞 联系方式

- **GitHub Issues**: https://github.com/IvanYangYangXi/artclaw/issues
- **团队沟通**: 通过 WorkBuddy 团队协作功能

## 📝 更新日志

### 2026-03-12
- ✅ 项目初始化
- ✅ 创建 GitHub 仓库
- ✅ 完成初始文档
- ✅ 建立团队协作规范
- ✅ 工程目录迁移至 `D:\MyProject\ArtClaw`

## 📄 许可证

待定

---

**最后更新**: 2026-03-12
**项目状态**: 初始阶段 🚀
**文档版本**: v1.0
