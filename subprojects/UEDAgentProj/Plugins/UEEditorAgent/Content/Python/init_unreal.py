import unreal

def sync_connection_state(is_online: bool):
    # 获取 C++ 子系统的单例对象
    subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
    
    if subsystem:
        # 调用 C++ 接口，触发状态更新和 UI 刷新委托
        subsystem.set_connection_status(is_online)
        unreal.log(f"Agent Status Synced: {is_online}")

# 测试：模拟连接成功
sync_connection_state(True)