# ArtClaw文档编写规范

## 0. 项目结构与编写原则

### 0.1 项目结构
**ArtClaw** 总项目包含多个DCC软件插件：
- UE_Editor_Agent (UE)
- Maya_Editor_Agent (未来)
- Blender_Editor_Agent (未来)

本文档适用于总项目及所有子项目。

### 0.2 编写原则
**所有AI生成的文档必须精简、无废话**：
- 删除冗余解释和重复说明
- 合并相关章节，使用紧凑的表格
- 精简示例代码注释，只保留关键说明
- 避免不必要的附录和辅助章节
- 使用直接明了的表述方式

目标：在保证核心内容和可操作性的前提下，最大限度减少token消耗。

---

## 1. 文档组织

### 1.1 目录结构
```
docs/
├── specs/                          # 通用规范（跨项目共享）
│   ├── AI文档编写规范.md
│   ├── 项目结构说明.md
│   └── 跨项目共享机制.md
│
├── UE_Editor_Agent/                # 子项目文档
│   ├── specs/                      # 子项目专属规范
│   ├── features/                   # 实现文档（按阶段组织）
│   └── decisions/                  # 决策记录（ADR格式）
│
└── Maya_Editor_Agent/              # 其他子项目...
```

### 1.2 文档分类

| 类型 | 路径 | 内容 | 维护者 |
| :--- | :--- | :--- | :--- |
| 通用规范 | `docs/specs/` | 跨项目共享的规范 | 项目负责人 |
| 子项目规范 | `docs/{Project}/specs/` | 软件专属规范 | 子项目负责人 |
| 实现文档 | `docs/{Project}/features/` | 详细实现指南 | AI助手 |
| 决策记录 | `docs/{Project}/decisions/` | ADR格式决策 | 开发团队 |

---

## 2. 编号与命名

### 2.1 子项目标识
- **UE_Editor_Agent**: UE
- **Maya_Editor_Agent**: MYA
- **Blender_Editor_Agent**: BLD

### 2.2 文档编号规则
格式：`阶段 X.Y：功能名称`

- **X**: 主阶段号（0=环境初始化，1=核心功能，2=增强功能）
- **Y**: 子步骤号（从1开始）

**示例**：
- `阶段 0.3：开发者菜单与可停靠窗口`
- `阶段 1.1：MCP通信网关`

### 2.3 文件命名
```
{X.Y} {功能名称}.md

# 示例
0.1 插件目录与模块骨架.md
0.3 开发者菜单与入口注册.md
1.2 MCP通信协议实现.md
```

### 2.4 跨项目功能编号
```
阶段 1.1：MCP通信网关 (UE)
阶段 1.1：MCP通信网关 (Maya)
```

---

## 3. 文档模板

### 3.1 实现文档模板（features/）
```markdown
# 阶段 X.Y：功能名称

**目标**：一句话说明本步骤要实现什么

**里程碑**：
1. 可验证的具体目标1
2. 可验证的具体目标2
3. 可验证的具体目标3

**适用范围**：☑ UE_Editor_Agent  ☐ Maya_Editor_Agent  ☐ 其他

---

## 1. 背景与上下文
说明为什么需要这个功能

## 2. 实现步骤
分步骤说明实现流程，每个步骤包含：
- 操作说明
- 代码示例（带语言标注）
- 注意事项

## 3. 核心代码
### 3.1 C++部分
```cpp
// 完整代码示例
```

### 3.2 Python部分
```python
# 完整代码示例
```

### 3.3 配置文件
```json
{
  "完整配置示例": "value"
}
```

## 4. 配置参数表
| 参数名 | 推荐值 | 说明 | 适用范围 |
| :--- | :--- | :--- | :--- |
| param1 | value1 | 说明1 | UE/Maya/通用 |

## 5. 验证清单
### 5.1 编译前检查
- [ ] 检查项1
- [ ] 检查项2

### 5.2 功能验证
- [ ] 功能点1验证方法
- [ ] 功能点2验证方法

### 5.3 高级验证
- [ ] 性能测试
- [ ] 内存泄漏检查

## 6. 常见问题
| 问题现象 | 可能原因 | 解决方案 |
| :--- | :--- | :--- |
| 问题描述 | 原因分析 | 解决步骤 |

## 7. 跨项目差异（如适用）
### UE_Editor_Agent 实现
- 特有实现细节1

### Maya_Editor_Agent 实现
- 特有实现细节2

## 8. 下一步建议
指明完成本步骤后应该做什么，链接到下一个文档

## 9. 变更历史
| 日期 | 版本 | 变更内容 | 作者 |
| :--- | :--- | :--- | :--- |
| 2026-03-14 | 1.0 | 初始版本 | AI助手 |
```

### 3.2 规范文档模板（specs/）
```markdown
# 规范名称

**版本**：1.0
**适用范围**：☑ 通用  ☐ UE_Editor_Agent  ☐ Maya_Editor_Agent  ☐ 其他

## 1. 目的
说明本规范的目标

## 2. 适用范围
明确适用哪些项目/模块

## 3. 具体规范
分条列出详细规则

## 4. 示例
提供正确和错误的示例对比

## 5. 例外情况
说明哪些情况可以不遵守本规范

## 6. 变更历史
记录规范的修订历史
```

---

## 4. 代码规范

### 4.1 C++规范
- **头文件**：必须包含`#pragma once`或`#ifndef`防护
- **类定义**：使用正确前缀（`F`, `U`, `A`, `S`）
- **实现分离**：.h和.cpp文件分开
- **注释**：关键逻辑使用`// NOTE:`, `// TODO:`, `// FIXME:`标注
- **格式化**：遵循UE官方代码规范

```cpp
#pragma once
#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "UEAgentSubsystem.generated.h"

// NOTE: 编辑器子系统，全局单例
UCLASS()
class UEEDITORAGENT_API UUEAgentSubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

private:
    // TODO: 添加线程安全机制
    bool bIsConnected;
};
```

### 4.2 Python规范
- **导入语句**：按标准库、第三方库、本地模块分组
- **类型注解**：函数参数和返回值必须添加类型注解
- **文档字符串**：模块、类、函数必须有docstring
- **错误处理**：使用try-except捕获异常并记录日志

```python
import sys
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

import unreal
from .logger import ue_log

def setup_python_paths(plugin_root: Path) -> bool:
    """设置Python路径，确保依赖可以正确导入
    
    Args:
        plugin_root: 插件根目录路径
        
    Returns:
        成功返回True，失败返回False
    """
    try:
        lib_path = plugin_root / "Content" / "Python" / "Lib"
        if not lib_path.exists():
            raise FileNotFoundError(f"路径不存在: {lib_path}")
        sys.path.insert(0, str(lib_path))
        return True
    except Exception as e:
        ue_log.error(f"设置Python路径失败: {e}")
        return False
```

### 4.3 配置文件规范
```json
{
  "plugin": {
    "name": "UEEditorAgent",
    "version": "1.0.0",
    "python_dependencies": {
      "required_packages": ["websockets", "pydantic"],
      "install_target": "Content/Python/Lib"
    }
  }
}
```

---

## 5. 命名规范

### 5.1 C++命名
| 类型 | 前缀 | 示例 | 说明 |
| :--- | :--- | :--- | :--- |
| Module类 | `F` | `FUEEditorAgentModule` | 继承自IModuleInterface |
| Subsystem类 | `U` | `UUEAgentSubsystem` | 继承自UEditorSubsystem |
| Slate Widget | `S` | `SUEAgentDashboardWidget` | Slate UI类 |
| 结构体 | `F` | `FAgentConfig` | 纯数据容器 |
| 枚举 | `E` | `EConnectionStatus` | 枚举类型 |

### 5.2 Python命名
- **模块名**：`snake_case`（`ue_agent.py`）
- **函数名**：`snake_case`（`setup_python_paths()`）
- **类名**：`PascalCase`（`UELogRedirector`）
- **常量**：`UPPER_SNAKE_CASE`（`LOG_CATEGORY = "UEAgent"`）
- **装饰器**：`@ue_agent.tool`

---

## 6. 术语表

### 6.1 通用术语
| 中文 | 英文 | 缩写 | 示例 |
| :--- | :--- | :--- | :--- |
| 里程碑 | Milestone | MS | MS-0.3完成 |
| 委托 | Delegate | - | OnStatusChanged委托 |
| 子系统 | Subsystem | - | UUEAgentSubsystem |
| 可停靠窗口 | Dockable Tab | Tab | Dashboard Tab |
| 插件 | Plugin | - | UEEditorAgent插件 |

### 6.2 MCP术语
| 中文 | 英文 | 说明 |
| :--- | :--- | :--- |
| 模型上下文协议 | Model Context Protocol (MCP) | 通信标准 |
| 工具 | Tool | MCP可调用的函数 |
| 资源 | Resource | MCP可访问的数据 |
| 提示 | Prompt | MCP可调用的模板 |
| 传输层 | Transport Layer | 通信实现（stdio/sse） |

---

## 7. 质量标准

### 7.1 文档完整性检查
- [ ] **目标明确**：每个步骤都有清晰的里程碑目标（3-5个）
- [ ] **代码完整**：所有代码示例可以直接复制使用，无语法错误
- [ ] **配置详尽**：配置参数有默认值、说明和适用范围
- [ ] **验证可执行**：每个验证项都有具体的操作步骤
- [ ] **编号一致**：与开发路线图的编号完全匹配
- [ ] **术语统一**：全文术语使用一致，符合术语表
- [ ] **路径正确**：所有路径引用使用正确格式
- [ ] **跨项目标识**：明确标注适用范围（UE/Maya/通用）
- [ ] **错误处理**：关键代码包含错误处理和日志记录
- [ ] **性能考虑**：复杂操作有性能说明和优化建议

### 7.2 代码示例质量
- [ ] 能独立编译/运行
- [ ] 包含必要的头文件/导入语句
- [ ] 关键行有注释说明
- [ ] 符合项目编码规范
- [ ] 使用实际项目中的类名和函数名
- [ ] 无硬编码的路径或配置

---

## 8. 更新与维护

### 8.1 何时更新文档
- [ ] 实现代码的接口或行为变更
- [ ] 新增功能或配置项
- [ ] 修复了文档中描述的错误
- [ ] 发现了新的问题或解决方案
- [ ] 性能优化改变了使用方式

### 8.2 更新流程
1. **标记待更新**：在文档顶部添加 `**状态**：待更新`
2. **创建任务**：在任务管理工具中创建更新任务
3. **同步修改**：同时更新代码和文档
4. **验证更新**：按照7.1-7.2检查清单验证
5. **记录变更**：在文档底部"变更历史"中记录
6. **移除标记**：验证完成后移除待更新标记

### 8.3 CHANGELOG格式
```markdown
# UE Editor Agent 变更日志

## [1.0.0-alpha] - 2026-03-14
### 新增
- 插件骨架和模块系统
- C++编辑器子系统
- Slate UI Dashboard
- Python日志重定向

### 文档更新
- 完善0.3文档：补充实时刷新机制
- 新建0.4日志系统文档

### 修复
- 修复编号不一致问题
```

---

## 9. 跨项目共享

### 9.1 共享文档类型
**位置**：`docs/specs/`
- AI文档编写规范
- Git工作流规范
- 代码审查规范
- 发布流程规范
- 术语表（通用部分）

### 9.2 子项目专属文档
**位置**：`docs/{Project}/`
- 开发路线图
- 系统架构设计
- 详细实现文档
- 软件专属术语

### 9.3 引用共享文档
```markdown
**规范说明**：
本步骤遵循 [AI文档编写规范](../../specs/AI文档编写规范.md) 的 3.1 节要求。
```

---

## 10. 常见问题

### 10.1 文档与代码不一致
1. **确认现状**：运行代码确认实际行为
2. **判断优先级**：
   - 代码正确，文档错误 → 更新文档
   - 文档正确，代码错误 → 修复代码
   - 都需改进 → 创建新任务
3. **同步更新**：保持文档和代码一致
4. **通知相关方**：在团队频道或任务管理工具中通知

### 10.2 编号冲突或重复
1. **检查路线图**：对照开发路线图确认正确编号
2. **批量重命名**：使用脚本批量修改文件名和内部引用
3. **更新链接**：检查并更新所有文档间的交叉引用
4. **记录变更**：在CHANGELOG中记录编号变更

---

**文档版本**：2.0（简化版）
**最后更新**：2026-03-14
**适用范围**：ArtClaw总项目及所有子项目
