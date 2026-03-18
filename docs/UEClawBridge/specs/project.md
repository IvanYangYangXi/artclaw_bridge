# 项目宪法：技术栈、编码风格、全局约定

* 定义项目的“灵魂”，包括使用的框架（如 Next.js + Tailwind）、目录规范、命名偏好等。AI 助手（如 Claude Code 或 Cursor）在执行任何任务前应首选阅读此文件。
* 在 AI 指令中内置“Read specs/project.md first”，确保其生成的代码符合项目既定规范。

## 1. 目录规范
/my-project
├── /docs                                  # 项目文档目录
│   └── /UEClawBridge                   # 子项目名称
│       └── /specs (或 /openspec)          # 规范核心目录
│           ├── project.md                 # 项目宪法：技术栈、编码风格、全局约定
│           ├── /features                  # 功能模块规格
│           ├── /api                       # 接口协议（OpenAPI/Swagger/JSON Schema）
│           │   └── api-spec.yaml
│           ├── /prototypes                # 原型说明（UI 交互、组件规范）
│           ├── /tests                     # 测试规格：明确 Acceptance Criteria (AC)
│           │   └── test-cases.md
│           └── /decisions                 # ADR (架构决策记录)
│               └── 001-use-postgresql.md
├── /src                           # AI 根据 specs 生成的源代码
│   └── /UEClawBridge           # 子项目名称
├── /tests                         # AI 根据 specs 生成的自动化脚本
└── .claudecode (或 .cursor)       # AI 助手的配置与指令集