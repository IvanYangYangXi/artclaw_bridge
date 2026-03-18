# OpenClaw vs WorkBuddy 配置对比

**文档版本**：1.0  
**创建日期**：2026-03-15  
**作者**：AI助手  
**状态**：✅ 已完成

---

## 📋 概述

本文档详细对比OpenClaw和WorkBuddy在UE Editor Agent集成中的配置差异，帮助开发者理解两种平台的特性并做出选择。

---

## 🔧 核心配置对比

### 1. 部署方式

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **部署类型** | 外部独立服务 | IDE内置插件 | OpenClaw需单独安装，WorkBuddy集成在IDE |
| **安装方式** | `pip install openclaw` | IDE内置/插件市场 | WorkBuddy安装更简单 |
| **启动方式** | 手动启动：`openclaw serve` | IDE启动时自动加载 | WorkBuddy更自动化 |
| **进程管理** | 独立进程 | IDE子进程 | WorkBuddy生命周期与IDE绑定 |

**配置示例对比**：

```json
// OpenClaw配置 (openclaw-config.json)
{
  "server": {
    "host": "localhost",
    "port": 8080,
    "auto_start": false
  }
}

// WorkBuddy配置 (workbuddy.settings.json)
{
  "mcpServers": {
    "ue-agent": {
      "url": "ws://localhost:8080",
      "autoConnect": true
    }
  }
}
```

---

### 2. MCP服务器配置

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **配置位置** | `openclaw-config.json` | IDE设置面板 | WorkBuddy图形化配置 |
| **配置格式** | JSON文件 | JSON + UI | WorkBuddy支持UI配置 |
| **热重载** | 需重启服务 | 实时生效 | WorkBuddy更灵活 |
| **配置校验** | 启动时检查 | 实时校验 | WorkBuddy即时反馈 |

**MCP配置对比**：

```json
// OpenClaw MCP配置
{
  "mcp": {
    "host": "localhost",
    "port": 8080,
    "protocol": "websocket",
    "reconnect": {
      "enabled": true,
      "attempts": 5,
      "delay": 1000
    }
  }
}

// WorkBuddy MCP配置
{
  "mcpServers": {
    "ue-editor-agent": {
      "type": "websocket",
      "url": "ws://localhost:8080/mcp",
      "autoConnect": true,
      "reconnectAttempts": 5,
      "reconnectDelay": 1000,
      "timeout": 30000
    }
  }
}
```

---

### 3. System Prompt配置

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **配置位置** | `system_prompt.txt` | IDE设置 | WorkBuddy支持多Prompt模板 |
| **动态更新** | 需重启 | 实时切换 | WorkBuddy更灵活 |
| **模板支持** | 单模板 | 多模板 | WorkBuddy支持场景切换 |
| **变量替换** | 基础 | 高级 | WorkBuddy支持复杂表达式 |

**Prompt配置对比**：

```json
// OpenClaw System Prompt
{
  "system_prompt": "你是一个UE助手。当前编辑器状态：{editor_mode}"
}

// WorkBuddy System Prompt配置
{
  "systemPrompt": {
    "dynamic": true,
    "sources": ["ue_editor_mode", "selected_assets"],
    "templates": {
      "level_editor": "关卡模式：可生成Actor",
      "blueprint": "蓝图模式：可创建节点"
    }
  }
}
```

---

### 4. 工具和资源管理

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **Tools发现** | 自动 | 自动 + 手动 | WorkBuddy支持手动添加 |
| **Resources订阅** | 全部订阅 | 选择性订阅 | WorkBuddy更节省资源 |
| **缓存策略** | 内存缓存 | 智能缓存 | WorkBuddy支持持久化缓存 |
| **同步频率** | 固定 | 可配置 | WorkBuddy更灵活 |

**Tools配置对比**：

```json
// OpenClaw Tools配置
{
  "tools": {
    "auto_discover": true,
    "cache_ttl": 3600
  }
}

// WorkBuddy Tools配置
{
  "tools": {
    "ue_editor": {
      "autoExecute": false,
      "requireConfirmation": ["delete"],
      "showPreview": true,
      "maxConcurrentCalls": 3
    }
  },
  "resources": {
    "autoRefresh": true,
    "refreshInterval": 1000,
    "cacheSize": 100
  }
}
```

---

### 5. 安全和风险管理

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **风险分级** | 4级 | 4级 | 相同 |
| **确认对话框** | 原生UI | IDE风格 | WorkBuddy更统一 |
| **白名单** | 支持 | 支持 | 相同 |
| **审计日志** | 文件 | IDE + 文件 | WorkBuddy双份记录 |

**安全配置对比**：

```json
// OpenClaw安全配置
{
  "security": {
    "risk_levels": ["low", "medium", "high", "critical"],
    "require_confirmation": ["delete", "format"],
    "whitelist": ["query", "get"]
  }
}

// WorkBuddy安全配置
{
  "riskManagement": {
    "enabled": true,
    "levels": {
      "critical": {
        "color": "#ef4444",
        "requireConfirm": true,
        "dialogType": "critical"
      }
    },
    "whitelistTools": ["query"]
  }
}
```

---

### 6. RAG知识库

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **向量库** | 外部 | 内置 | WorkBuddy集成更好 |
| **索引构建** | 手动 | 自动/手动 | WorkBuddy支持自动 |
| **检索模型** | 可配置 | 内置+可配置 | WorkBuddy有默认模型 |
| **Prompt注入** | 手动 | 自动 | WorkBuddy更智能 |

**RAG配置对比**：

```json
// OpenClaw RAG配置
{
  "rag": {
    "vector_store": "faiss",
    "model": "all-MiniLM-L6-v2",
    "auto_index": false
  }
}

// WorkBuddy RAG配置
{
  "rag": {
    "enabled": true,
    "embeddingModel": "all-MiniLM-L6-v2",
    "searchParameters": {
      "topK": 5,
      "scoreThreshold": 0.7
    },
    "autoIndexing": {
      "enabled": true,
      "rebuildCron": "0 2 * * *"
    }
  }
}
```

---

### 7. Skill系统

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **热加载** | ✅ 支持 | ✅ 支持 | 相同 |
| **市场** | ClawHub | WorkBuddy市场 | 不同平台 |
| **依赖管理** | pip | 内置+pip | WorkBuddy集成更好 |
| **版本控制** | Git | Git + 内置 | WorkBuddy更完善 |

**Skill配置对比**：

```json
// OpenClaw Skill配置
{
  "skills": {
    "directory": "./skills",
    "hot_reload": true,
    "marketplace": "https://clawhub.io"
  }
}

// WorkBuddy Skill配置
{
  "skills": {
    "enabled": true,
    "directories": ["./skills"],
    "hotReload": {
      "enabled": true,
      "autoInstallDependencies": true
    },
    "marketplace": {
      "enabled": true,
      "sources": [...],
      "autoUpdate": {
        "checkIntervalHours": 24
      }
    }
  }
}
```

---

### 8. 日志和监控

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **日志位置** | `~/.openclaw/logs` | `~/.workbuddy/logs` | 不同目录 |
| **日志级别** | DEBUG-ERROR | VERBOSE-ERROR | WorkBuddy更细 |
| **日志轮转** | 文件大小 | 时间+大小 | WorkBuddy更完善 |
| **审计日志** | 文件 | IDE + 文件 | WorkBuddy双份 |

**日志配置对比**：

```json
// OpenClaw日志配置
{
  "logging": {
    "level": "info",
    "file": "~/.openclaw/logs/openclaw.log",
    "maxSize": "10MB"
  }
}

// WorkBuddy日志配置
{
  "logging": {
    "level": "info",
    "mcp": {
      "level": "debug",
      "file": "./logs/mcp.log"
    }
  }
}
```

---

### 9. 性能参数

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **超时时间** | 30s | 30s | 相同 |
| **重试次数** | 5 | 5 | 相同 |
| **缓存大小** | 1000 | 100 | WorkBuddy更保守 |
| **并发限制** | 10 | 3 | WorkBuddy更谨慎 |

---

### 10. IDE集成

| 配置项 | OpenClaw | WorkBuddy | 差异说明 |
| :--- | :--- | :--- | :--- |
| **UI集成** | 外部窗口 | 内置面板 | WorkBuddy更统一 |
| **快捷键** | 可配置 | 可配置 | 相同 |
| **主题同步** | 手动 | 自动 | WorkBuddy更智能 |
| **状态栏** | 无 | 有 | WorkBuddy显示连接状态 |

---

## 📊 总体对比表

| 特性类别 | OpenClaw | WorkBuddy | 推荐场景 |
| :--- | :--- | :--- | :--- |
| **部署复杂度** | ⭐⭐⭐ | ⭐ | WorkBuddy更适合个人 |
| **配置灵活性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | OpenClaw更灵活 |
| **IDE集成** | ⭐⭐ | ⭐⭐⭐⭐⭐ | WorkBuddy更深度 |
| **RAG能力** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | WorkBuddy更强大 |
| **Skill生态** | ⭐⭐⭐⭐ | ⭐⭐⭐ | OpenClaw更成熟 |
| **安全性** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | WorkBuddy更完善 |
| **学习曲线** | 陡峭 | 平缓 | WorkBuddy更易用 |

---

## 🎯 选择建议

### 使用OpenClaw的场景
- ✅ 需要高度自定义配置
- ✅ 团队已有OpenClaw基础设施
- ✅ 需要访问ClawHub大量技能
- ✅ 跨多个IDE/工具使用
- ✅ 有专门运维人员

### 使用WorkBuddy的场景
- ✅ 个人开发者或小团队
- ✅ 主要使用Cloud Studio/VS Code
- ✅ 需要强大的RAG能力
- ✅ 希望开箱即用
- ✅ 重视IDE集成体验

### 双平台支持
- ✅ 大型团队，不同成员偏好不同
- ✅ 需要平滑迁移过渡
- ✅ 评估阶段，需要对比测试

---

## 🔧 配置迁移工具

### OpenClaw → WorkBuddy 配置转换

```python
# 配置转换脚本
import json

def convert_openclaw_to_workbuddy(openclaw_config):
    """转换OpenClaw配置为WorkBuddy格式"""
    
    wb_config = {
        "mcpServers": {},
        "logging": {},
        "skills": {}
    }
    
    # 转换MCP配置
    if "mcp" in openclaw_config:
        mcp = openclaw_config["mcp"]
        wb_config["mcpServers"]["ue-agent"] = {
            "type": "websocket",
            "url": f"ws://{mcp['host']}:{mcp['port']}/mcp",
            "autoConnect": True,
            "reconnectAttempts": 5
        }
    
    # 转换日志配置
    if "logging" in openclaw_config:
        wb_config["logging"]["level"] = openclaw_config["logging"]["level"]
    
    return wb_config

# 使用示例
with open("openclaw-config.json") as f:
    oc_config = json.load(f)

wb_config = convert_openclaw_to_workbuddy(oc_config)

with open("workbuddy.settings.json", "w") as f:
    json.dump(wb_config, f, indent=2)
```

---

## 📚 参考配置模板

### 生产环境推荐配置

#### OpenClaw生产配置
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "workers": 4
  },
  "security": {
    "risk_levels": ["low", "medium", "high", "critical"],
    "require_confirmation": ["delete", "format", "system"]
  },
  "logging": {
    "level": "warning",
    "audit_log": "/var/log/openclaw/audit.log"
  }
}
```

#### WorkBuddy生产配置
```json
{
  "mcpServers": {
    "ue-production": {
      "type": "websocket",
      "url": "ws://ue-server.internal:8080/mcp",
      "autoConnect": true,
      "timeout": 60000
    }
  },
  "logging": {
    "level": "warning"
  },
  "riskManagement": {
    "enabled": true,
    "levels": {
      "critical": {
        "requireConfirm": true,
        "requireApproval": true
      }
    }
  }
}
```

---

## 📝 变更历史

| 版本 | 日期 | 作者 | 变更 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-03-15 | AI助手 | 初始版本，完整对比 |

---

**文档状态**：✅ 已完成  
**维护状态**：活跃维护  
**最后更新**：2026-03-15 00:35
