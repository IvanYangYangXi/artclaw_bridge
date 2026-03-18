# UE Editor Agent - Skill 模块标准定义 (v1.0)

## 1. 模块设计理念
- **自描述性**：每个 Skill 包含完整的元数据，AI 能自动理解其用途。
- **混合驱动**：支持 Python 逻辑控制、C++ 底层调用及 UMG 界面交互。
- **热插拔**：无需重启 UE 编辑器即可安装或更新技能。

## 2. 目录结构规范
一个标准的 Skill 模块以文件夹形式存在，建议命名为 `Skill_FunctionName`。

```text
Skill_SceneGenerator/
├── manifest.json            # 核心描述文件：定义名称、版本、权限及入口
├── scripts/                 # 逻辑代码
│   ├── main.py              # 主要 Python 逻辑 (入口)
│   └── utils.py             # 辅助脚本
├── binaries/                # (可选) 编译好的 C++ 扩展 (DLL/Lib)
├── ui/                      # (可选) 关联的 UE 资源
│   └── WBP_ConfirmPanel.uasset # 原生 UMG 界面资产
└── SKILL.md                 # AI 文档 + OpenClaw/ClawHub 分发
```

## 3. 核心配置文件 (`manifest.json`)
该文件是 OpenClaw 与 UE 识别技能的桥梁。

```json
{
  "id": "com.yourname.scene_generator",
  "version": "1.0.2",
  "displayName": "智能场景生成器",
  "description": "根据自然语言描述自动摆放室内家具并调整灯光",
  "author": "EditorAgentTeam",
  "minUEVersion": "5.3",
  "entryPoint": "scripts/main.py",
  "mcp_tools": [
    {
      "name": "generate_room_layout",
      "description": "生成房间布局",
      "parameters": {
        "style": "string",
        "room_type": "string"
      }
    }
  ],
  "dependencies": {
    "python_libs": ["numpy", "requests"],
    "plugins": ["ProceduralContentGeneration"]
  }
}
```

## 4. 技能同步与加载流程

### 4.1 发布阶段 (Publishing)
1. 开发者将上述文件夹打包为 `.zip` 或推送至 Git 仓库。
2. 在 OpenClaw 的 **Skill Hub** 注册该模块的元数据。

### 4.2 安装与激活 (Syncing)
1. **OpenClaw 端**：用户点击“安装”，OpenClaw 将包下载至本地 `Skills` 缓存目录。
2. **UE 端同步**：UE 插件通过 WebSocket 接收到新技能通知，将 `scripts/` 路径添加至 `sys.path`。
3. **MCP 注册**：UE 插件解析 `manifest.json` 中的 `mcp_tools` 字段，动态向 OpenClaw 宣告新的工具接口。

### 4.3 执行阶段 (Execution)
- 当用户输入“帮我布置一个极简风客厅”：
- OpenClaw 识别到该需求匹配 `generate_room_layout` 工具。
- 发送指令给 UE 插件，插件定位到 `scripts/main.py` 执行对应函数。
- 如果需要用户确认，Python 脚本调用 **Native UI Manager** 弹出 `ui/WBP_ConfirmPanel`。

## 5. 安全与共享建议
- **沙盒化**：通过 `manifest.json` 声明权限（如：是否允许修改文件、是否允许访问网络）。
- **版本控制**：支持多版本并存，确保生产环境的稳定性。
- **一键分享**：支持生成 `openclaw://install-skill?url=...` 这种协议链接，实现社区内快速分享。

---
**提示**：为了实现“热加载”，建议在 UE 插件中实现一个 `SkillLoader` 单例，负责监控技能文件夹的变化并自动执行 `importlib.reload()`。
