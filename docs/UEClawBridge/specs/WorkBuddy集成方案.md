# WorkBuddy 集成方案

> **定位**：WorkBuddy是AI Agent平台层的第一个接入目标，与UE插件之间通过MCP协议通信。本文档描述UE + WorkBuddy完整链路的集成方案，也是ArtClaw整套基建的第一个实战验证（现改为UE + openClaw优先）。

---

## 一、在总架构中的位置

```
WorkBuddy（AI Agent平台）
       │ MCP over WebSocket/stdio
       │
Platform Manager（ArtClaw）
       │ 路由到对应DCC实例
       │
openclaw-mcp-bridge（MCP Server @ localhost:7001）
       │
UEClawBridge Plugin
       │ 命令队列 → 主线程执行
       │
UE Editor API（Python + C++）
```

WorkBuddy 作为 MCP Client，UE插件内嵌的 MCP Server 作为 MCP Server 端，双方通过标准MCP协议通信，中间的 Platform Manager 负责连接管理。

---

## 二、连接配置

WorkBuddy 侧在 MCP 配置中添加 UE Editor Agent 服务器：

```json
{
  "mcpServers": {
    "ue-editor-agent": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server"],
      "env": {
        "PYTHONPATH": "D:/MyProject/ArtClaw/openclaw-mcp-bridge"
      }
    }
  }
}
```

> stdio 为本地单客户端模式（推荐开发阶段使用）。多客户端并发时切换为 WebSocket，端口默认 7001。

---

## 三、UE插件侧设计要点

与总架构一致，UE侧几个关键机制：

**Skill Hub（统一管理）**：所有Skill在UE插件侧注册，WorkBuddy通过 `tools/list` 自动发现可用Skill，无需手动配置。

**按需拉取 + 关键推送**：
- AI需要UE上下文时主动调用 `resources/unreal://level/selected_actors` 等接口获取
- UE侧仅推送关键事件（Skill热重载、关卡切换、事务提交），避免Token浪费

**主线程安全**：WorkBuddy发来的Skill调用请求经命令队列，由UE主线程Tick消费执行，结果异步回传。

**关键推送事件**：
```
notifications/skills/reloaded    # Skill热重载后通知WorkBuddy更新缓存
notifications/editor/mode_changed
notifications/level/loaded
notifications/transaction/committed
```

---

## 四、与 OpenClaw 的关系

WorkBuddy 和 OpenClaw 是**平行的两个AI平台接入**，UE插件侧不区分来源，两者通过同一套 MCP 接口接入，共享同一个 Skill Hub。

| 维度 | WorkBuddy | OpenClaw |
|------|-----------|----------|
| 当前状态 | ✅ 第一接入目标 | 📋 并行支持 |
| 连接方式 | stdio / WebSocket | stdio / WebSocket |
| Skill来源 | UE插件侧统一管理 | UE插件侧统一管理 |
| 差异 | 集成在IDE中，调试体验好 | 独立运行，轻量 |

---

## 五、分阶段实施

| 阶段 | WorkBuddy侧任务 | 完成标准 |
|------|----------------|---------|
| **基础连接** | 配置MCP服务器地址，建立连接 | WorkBuddy能列出UE暴露的Skill列表 |
| **Skill调用** | 通过自然语言触发Skill，验证执行 | UE场景中操作结果符合预期 |
| **上下文同步** | 验证按需拉取和关键推送 | 编辑器状态变化时WorkBuddy能感知 |
| **高风险确认** | 高风险操作触发UE侧确认对话框 | AI操作前弹出确认，可撤销 |

---

## 六、验证清单

- [ ] WorkBuddy连接UE MCP Server成功
- [ ] `tools/list` 返回正确Skill列表
- [ ] 自然语言指令能触发对应Skill执行
- [ ] UE场景变化（如创建Actor）结果正确
- [ ] Skill热重载后WorkBuddy立即感知
- [ ] 高风险操作触发确认对话框
- [ ] 操作可通过 Ctrl+Z 撤销

---

**版本**：2.0 | **更新**：2026-03-15 | **状态**：当前实施重点
