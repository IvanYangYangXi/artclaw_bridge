"""
UE Editor Agent 初始化脚本
在UE编辑器启动时自动执行
"""

import unreal
import sys
from pathlib import Path


# 设置Python路径
def setup_python_paths():
    """设置Python路径，确保依赖可以正确导入"""
    try:
        plugin_root = Path(unreal.Paths.project_plugins_dir()) / "UEEditorAgent"
        python_lib_path = plugin_root / "Content" / "Python" / "Lib"
        
        if python_lib_path.exists():
            if str(python_lib_path) not in sys.path:
                sys.path.insert(0, str(python_lib_path))
                unreal.log(f"[UEAgent] 添加Python路径: {python_lib_path}")
        else:
            unreal.log_warning(f"[UEAgent] Python Lib目录不存在: {python_lib_path}")
            
    except Exception as e:
        unreal.log_error(f"[UEAgent] 设置Python路径失败: {e}")


# 重定向日志
def setup_log_redirection():
    """设置Python日志重定向到UE Output Log"""
    try:
        import logging
        
        # 创建UE日志处理器
        class UELogHandler(logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    if record.levelno >= logging.ERROR:
                        unreal.log_error(msg)
                    elif record.levelno >= logging.WARNING:
                        unreal.log_warning(msg)
                    else:
                        unreal.log(msg)
                except Exception:
                    self.handleError(record)
        
        # 配置根日志记录器
        handler = UELogHandler()
        handler.setFormatter(logging.Formatter('[UEAgent] %(levelname)s: %(message)s'))
        
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
        
        unreal.log("[UEAgent] Python日志重定向已配置")
        
    except Exception as e:
        unreal.log_error(f"[UEAgent] 设置日志重定向失败: {e}")


# 启动MCP服务器
def start_mcp_on_editor_startup():
    """在编辑器启动时启动MCP服务器"""
    try:
        # 延迟启动，确保编辑器完全加载
        unreal.log("[UEAgent] 准备启动MCP服务器...")
        
        # 导入mcp_server模块
        from mcp_server import start_mcp_server
        
        # 启动服务器（异步）
        success = start_mcp_server(host="localhost", port=8080)
        if success:
            unreal.log("[UEAgent] MCP服务器启动命令已发送")
        else:
            unreal.log_error("[UEAgent] MCP服务器启动失败")
            
    except Exception as e:
        unreal.log_error(f"[UEAgent] 启动MCP服务器时发生错误: {e}")
        import traceback
        unreal.log_error(traceback.format_exc())


def sync_connection_state(is_online: bool):
    """供外部调用的状态同步函数"""
    # 获取 C++ 子系统的单例对象
    subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
    
    if subsystem:
        # 调用 C++ 接口，触发状态更新和 UI 刷新委托
        subsystem.set_connection_status(is_online)
        unreal.log(f"Agent Status Synced: {is_online}")


# 编辑器启动回调
@unreal.uclass()
class UEAgentStartup(unreal.SlatePostTick):
    """编辑器启动后的回调类"""
    
    def __init__(self):
        super().__init__()
        self.has_started = False
    
    def tick(self, delta_time: float):
        """每帧调用的Tick函数"""
        if not self.has_started:
            self.has_started = True
            start_mcp_on_editor_startup()


# 主初始化函数
def main():
    """主初始化入口"""
    try:
        unreal.log("=" * 60)
        unreal.log("UE Editor Agent 初始化开始")
        unreal.log("=" * 60)
        
        # 1. 设置Python路径
        setup_python_paths()
        
        # 2. 设置日志重定向
        setup_log_redirection()
        
        # 3. 注册启动回调
        # NOTE: 使用 SlatePostTick 确保在编辑器完全加载后启动
        startup_callback = UEAgentStartup()
        unreal.register_slate_post_tick_callback(startup_callback)
        
        unreal.log("[UEAgent] 初始化完成，等待编辑器启动...")
        
    except Exception as e:
        unreal.log_error(f"[UEAgent] 初始化失败: {e}")
        import traceback
        unreal.log_error(traceback.format_exc())


# 执行初始化
if __name__ == "__main__":
    main()