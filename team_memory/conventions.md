# Conventions

> 项目规范与约定。仅首条消息注入。

- [All] 代码文件黄金区间 100-300 行，硬性上限 500 行
- [All] 用户可见文本必须中文，指令/工具名/JSON key 保持英文
- [UE] C++ UI 新增文本必须在 UEAgentLocalization.cpp 注册中英文对
- [UE] Python Skill 的 error/message 字段用中文
- [UE] Skill 命名规范: {dcc}{major_version}_{skill_name}，如 ue5_material_node_edit
- [All] MCP 工具每个 DCC 只保留 1 个: run_ue_python(UE) / run_python(Maya/Max)
- [All] Skill 安装目录统一为 ~/.openclaw/workspace/skills/（项目源码 skills/ 是未安装状态）
- [UE] UE Slate Widget 按 Tab 拆文件，每个 200-600 行，修改互不干扰
- [All] install.bat 部署后自动运行 verify_sync 校验共享模块一致性
- [Maya] Maya 运行时加载安装目录文件，改源码后必须同步复制到安装目录
