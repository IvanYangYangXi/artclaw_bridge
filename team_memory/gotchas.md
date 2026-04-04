# Gotchas

> 反直觉行为、API 陷阱、容易犯的错误。每次 briefing 必读。

- [UE] Rotator 构造参数顺序是 Pitch,Yaw,Roll，不是 Roll,Pitch,Yaw
- [UE] GetUserFocusedWidget() 打字时焦点在输入框，不能用来检测面板聚焦
- [UE] RebuildMessageList 用索引遍历，不能用 const ref（lambda 捕获索引会出问题）
- [UE] SButton("NoBorder") 适合折叠/展开小按钮，不占空间
- [UE] Gateway content blocks 是累积的(delta 含之前 toolCall)，必须 seen_tool_ids 去重
- [UE] stream.jsonl 扩展新事件类型时，C++ 解析侧必须同步更新（否则静默忽略）
- [UE] init_skill_hub() 必须用函数初始化，直接 SkillHub() 构造全局实例为 None
- [Maya] 脚本编辑器不显示 Python logging 输出，启动代码必须用 print
- [Maya] from xxx import 裸导入需要模块目录在 sys.path 上，core/ 默认不在
- [Python] @staticmethod 和 self 参数互斥，加了 self 必须去掉装饰器
- [Python] Qt clicked signal 的 checked 参数不一致，lambda 要用 _checked=False 默认值
- [All] 等轴测 yaw 旋转必须绕 Z 轴(Rz)不是 Y 轴(Ry)，否则 Y 方向严重拉伸
- [All] 相机位置 = scene_center - depth_direction * distance，depth_dir 指向远离相机方向
- [UE] skill_hub 扫描要跳过 templates/ 目录（含 TODO 占位符会验证失败）
- [UE] DCC Context 提示词对弱模型要用"禁止"语气，不要用"应优先/建议"
- [UE] bridge_core _handle_chat_event 必须按 session key 过滤，否则多 DCC 串消息
- [All] session key 必须全局唯一，用时间戳后缀 agent/client:timestamp
- [All] tools.allow 必须用通配符 mcp_xxx_*，精确列举会漏掉新增工具
