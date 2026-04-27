"""
static_guard.py - 静态指令预审 (Static Guard)
===============================================

阶段 1.3: 使用 Python ast 模块在代码执行前进行安全扫描。

宪法约束:
  - 开发路线图 §1.3: 使用 ast 模块扫描代码，拦截黑名单
    (os.system, subprocess, __import__)，从源头切断系统级破坏
  - 核心机制 §3: 安全可逆执行

设计原则:
  - 静态优于动态：AST 层面拦截，不执行代码
  - 白名单优先：默认拒绝危险操作，显式允许
  - 可配置：支持自定义策略
  - 可审计：记录所有拦截日志
"""

import ast
from enum import IntEnum
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from claw_bridge_logger import UELogger


# ============================================================================
# 1. 风险等级定义
# ============================================================================

class RiskLevel(IntEnum):
    """风险等级"""
    SAFE = 0        # 安全
    LOW = 1         # 低风险 (日志记录)
    MEDIUM = 2      # 中风险 (需审核)
    HIGH = 3        # 高风险 (默认阻止)
    CRITICAL = 4    # 致命风险 (始终阻止)


@dataclass
class SecurityIssue:
    """安全扫描发现的问题"""
    level: RiskLevel
    message: str
    line: int = 0
    col: int = 0
    node_type: str = ""


@dataclass
class ScanResult:
    """扫描结果"""
    safe: bool = True
    blocked: bool = False
    issues: List[SecurityIssue] = field(default_factory=list)
    max_risk: RiskLevel = RiskLevel.SAFE

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "blocked": self.blocked,
            "max_risk": self.max_risk.name,
            "issues": [
                {
                    "level": i.level.name,
                    "message": i.message,
                    "line": i.line,
                    "col": i.col,
                }
                for i in self.issues
            ],
        }


# ============================================================================
# 2. 黑名单定义
# ============================================================================

# 危险模块 - 导入即阻止
# 注意: shutil 已移至阶段 5.6 文件操作确认系统处理
_BLOCKED_IMPORTS = {
    "subprocess", "ctypes", "socket",
    "http", "urllib", "requests", "ftplib", "smtplib",
    "multiprocessing", "signal", "pty", "resource",
}

# 危险函数调用 - 模块.函数 格式
_BLOCKED_CALLS = {
    # os 模块危险函数
    "os.system", "os.popen", "os.exec", "os.execl", "os.execle",
    "os.execlp", "os.execlpe", "os.execv", "os.execve", "os.execvp",
    "os.execvpe", "os.spawnl", "os.spawnle", "os.spawnlp",
    "os.spawnlpe", "os.spawnv", "os.spawnve", "os.spawnvp",
    "os.spawnvpe", "os.fork", "os.forkpty", "os.kill", "os.killpg",
    # 注意: os.remove/unlink/rmdir/rename 和 shutil.rmtree/move 已移至
    # 阶段 5.6 文件操作确认系统处理，不再在此阻止
    # builtins
    "eval", "compile", "__import__",
}

# os 模块中允许的安全函数（白名单）
_ALLOWED_OS_CALLS = {
    "os.path.join", "os.path.exists", "os.path.basename",
    "os.path.dirname", "os.path.abspath", "os.path.isfile",
    "os.path.isdir", "os.path.splitext", "os.path.split",
    "os.path.normpath", "os.path.relpath",
    "os.getcwd", "os.listdir", "os.walk",
    "os.environ.get", "os.getenv",
}

# 敏感路径 - 访问即阻止
_SENSITIVE_PATHS = [
    "C:\\Windows", "C:/Windows",
    "C:\\Program Files", "C:/Program Files",
    "System32", "system32",
]


# ============================================================================
# 3. AST 扫描器
# ============================================================================

class ASTScanner(ast.NodeVisitor):
    """
    基于 AST 的静态安全扫描器。

    宪法约束:
      - 开发路线图 §1.3: 使用 Python ast 模块扫描
      - 核心机制 §3: 安全可逆执行
    """

    def __init__(self, allowed_calls: set = None):
        self.issues: List[SecurityIssue] = []
        self._allowed_calls = allowed_calls or set()

    def _add_issue(self, level: RiskLevel, message: str, node: ast.AST):
        self.issues.append(SecurityIssue(
            level=level,
            message=message,
            line=getattr(node, "lineno", 0),
            col=getattr(node, "col_offset", 0),
            node_type=type(node).__name__,
        ))

    def _get_call_name(self, node: ast.Call) -> str:
        """从 Call 节点提取函数全名"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""

    # --- 访问器 ---

    def visit_Import(self, node: ast.Import):
        """检查 import 语句"""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name in _BLOCKED_IMPORTS:
                self._add_issue(
                    RiskLevel.CRITICAL,
                    f"Blocked import: '{alias.name}' (security risk)",
                    node,
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """检查 from ... import 语句"""
        if node.module:
            root_module = node.module.split(".")[0]
            if root_module in _BLOCKED_IMPORTS:
                self._add_issue(
                    RiskLevel.CRITICAL,
                    f"Blocked import: 'from {node.module} import ...' (security risk)",
                    node,
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """检查函数调用"""
        call_name = self._get_call_name(node)
        if not call_name:
            self.generic_visit(node)
            return

        # 检查白名单
        if call_name in self._allowed_calls or call_name in _ALLOWED_OS_CALLS:
            self.generic_visit(node)
            return

        # 检查黑名单
        if call_name in _BLOCKED_CALLS:
            self._add_issue(
                RiskLevel.CRITICAL,
                f"Blocked call: '{call_name}()' (security risk)",
                node,
            )

        # 检查 __import__
        if call_name == "__import__":
            self._add_issue(
                RiskLevel.CRITICAL,
                "Blocked: __import__() (use regular import instead)",
                node,
            )

        # 检查 exec/eval 嵌套
        if call_name in ("exec", "eval", "compile"):
            self._add_issue(
                RiskLevel.HIGH,
                f"Nested '{call_name}()' call detected (potential sandbox escape)",
                node,
            )

        # 检查 open() 写模式
        # 阶段 5.6: 降级为 MEDIUM，由文件操作确认系统处理
        if call_name == "open" and len(node.args) >= 2:
            mode_arg = node.args[1]
            if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                if any(c in mode_arg.value for c in ("w", "a", "x")):
                    self._add_issue(
                        RiskLevel.MEDIUM,
                        f"File write operation: open(..., '{mode_arg.value}') (handled by confirmation)",
                        node,
                    )

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        """检查字符串常量中的敏感路径"""
        if isinstance(node.value, str):
            for sensitive in _SENSITIVE_PATHS:
                if sensitive in node.value:
                    self._add_issue(
                        RiskLevel.HIGH,
                        f"Sensitive path reference: '{node.value[:80]}...'",
                        node,
                    )
                    break
        self.generic_visit(node)


# ============================================================================
# 3b. 文件操作风险检测器 (阶段 5.6)
# ============================================================================

# 中风险文件操作 — 需弹窗确认
_MEDIUM_RISK_FILE_OPS = {
    "os.rename", "os.replace", "shutil.move",
    "unreal.EditorAssetLibrary.rename_asset",
}

# 高风险文件操作 — 必须弹窗确认
_HIGH_RISK_FILE_OPS = {
    "os.remove", "os.unlink", "os.rmdir", "os.removedirs",
    "shutil.rmtree",
    "unreal.EditorAssetLibrary.delete_asset",
    "unreal.EditorAssetLibrary.delete_directory",
}

# 合并所有需确认的文件操作
_ALL_CONFIRMABLE_FILE_OPS = _MEDIUM_RISK_FILE_OPS | _HIGH_RISK_FILE_OPS


@dataclass
class FileOperationRisk:
    """文件操作风险评估结果"""
    needs_confirmation: bool = False
    risk_level: str = "safe"          # "safe", "medium", "high"
    operations: List[dict] = field(default_factory=list)
    is_batch: bool = False
    code_preview: str = ""


class FileOpDetector(ast.NodeVisitor):
    """
    检测代码中的文件操作及其风险等级。

    阶段 5.6: 文件修改/删除/批量操作弹窗确认
    """

    def __init__(self):
        self.detected_ops: List[dict] = []
        self._in_loop_depth = 0  # 循环嵌套深度

    def _get_call_name(self, node: ast.Call) -> str:
        """从 Call 节点提取函数全名"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""

    def visit_For(self, node: ast.For):
        self._in_loop_depth += 1
        self.generic_visit(node)
        self._in_loop_depth -= 1

    def visit_While(self, node: ast.While):
        self._in_loop_depth += 1
        self.generic_visit(node)
        self._in_loop_depth -= 1

    def visit_Call(self, node: ast.Call):
        call_name = self._get_call_name(node)
        if not call_name:
            self.generic_visit(node)
            return

        # 检查高风险文件操作
        if call_name in _HIGH_RISK_FILE_OPS:
            risk = "high"
            op_type = "delete" if any(kw in call_name for kw in ("remove", "unlink", "rmdir", "rmtree", "delete")) else "modify"
            self.detected_ops.append({
                "op": op_type,
                "call": call_name,
                "line": getattr(node, "lineno", 0),
                "in_loop": self._in_loop_depth > 0,
                "risk": risk,
            })
        # 检查中风险文件操作
        elif call_name in _MEDIUM_RISK_FILE_OPS:
            risk = "medium"
            op_type = "rename" if "rename" in call_name else "move"
            self.detected_ops.append({
                "op": op_type,
                "call": call_name,
                "line": getattr(node, "lineno", 0),
                "in_loop": self._in_loop_depth > 0,
                "risk": risk,
            })
        # 检查 open() 写模式
        elif call_name == "open":
            mode_val = None
            # 位置参数
            if len(node.args) >= 2:
                mode_arg = node.args[1]
                if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                    mode_val = mode_arg.value
            # 关键字参数 mode=
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    mode_val = kw.value.value
            if mode_val and any(c in mode_val for c in ("w", "a", "x")):
                self.detected_ops.append({
                    "op": "write_file",
                    "call": f"open(..., '{mode_val}')",
                    "line": getattr(node, "lineno", 0),
                    "in_loop": self._in_loop_depth > 0,
                    "risk": "medium",
                })

        self.generic_visit(node)


def detect_file_operations(code: str) -> FileOperationRisk:
    """
    检测代码中的文件操作并评估风险。

    Returns:
        FileOperationRisk 包含是否需要确认、风险等级、操作列表等。
    """
    result = FileOperationRisk()

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return result  # 语法错误不做文件操作检测

    detector = FileOpDetector()
    detector.visit(tree)

    if not detector.detected_ops:
        return result

    result.operations = detector.detected_ops
    result.needs_confirmation = True

    # 确定总体风险等级
    has_high = any(op["risk"] == "high" for op in detector.detected_ops)
    has_loop = any(op.get("in_loop", False) for op in detector.detected_ops)
    result.is_batch = has_loop

    if has_high or has_loop:
        result.risk_level = "high"
    else:
        result.risk_level = "medium"

    # 代码预览 (截取相关行)
    lines = code.split("\n")
    relevant_lines = set()
    for op in detector.detected_ops:
        line_no = op.get("line", 0)
        if 0 < line_no <= len(lines):
            relevant_lines.add(line_no)
    preview_parts = [f"L{ln}: {lines[ln-1].strip()}" for ln in sorted(relevant_lines)]
    result.code_preview = "\n".join(preview_parts[:10])  # 最多 10 行

    return result


# ============================================================================
# 4. StaticGuard 主接口
# ============================================================================

class StaticGuard:
    """
    静态指令预审主入口。

    宪法约束:
      - 开发路线图 §1.3: 执行前拦截黑名单
      - 核心机制 §3: 安全可逆执行

    用法::

        guard = StaticGuard()
        result = guard.check_code("import os; os.system('rm -rf /')")
        if result.blocked:
            print("Code blocked:", result.issues)
    """

    def __init__(self, block_threshold: RiskLevel = RiskLevel.HIGH,
                 allowed_calls: set = None):
        """
        Args:
            block_threshold: 大于等于此级别的问题会导致代码被阻止
            allowed_calls: 额外允许的函数调用白名单
        """
        self._block_threshold = block_threshold
        self._allowed_calls = allowed_calls or set()

    def check_code(self, code: str) -> ScanResult:
        """
        扫描代码安全性。

        Args:
            code: 要扫描的 Python 代码字符串

        Returns:
            ScanResult 包含安全性评估和发现的问题列表
        """
        result = ScanResult()

        # 1. 尝试解析 AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            result.issues.append(SecurityIssue(
                level=RiskLevel.LOW,
                message=f"Syntax error (will be caught at runtime): {e}",
                line=e.lineno or 0,
                col=e.offset or 0,
            ))
            # 语法错误不阻止（exec 会捕获），但标记为不安全
            result.safe = False
            return result

        # 2. 运行 AST 扫描器
        scanner = ASTScanner(allowed_calls=self._allowed_calls)
        scanner.visit(tree)
        result.issues = scanner.issues

        # 3. 评估风险
        if result.issues:
            result.max_risk = max(i.level for i in result.issues)
            result.safe = result.max_risk < RiskLevel.MEDIUM
            result.blocked = result.max_risk >= self._block_threshold

        # 4. 记录日志
        if result.blocked:
            issue_summary = "; ".join(
                f"L{i.line}: {i.message}" for i in result.issues
                if i.level >= self._block_threshold
            )
            UELogger.warning(f"Static Guard BLOCKED code: {issue_summary}")
        elif not result.safe:
            UELogger.debug(f"Static Guard warnings: {len(result.issues)} issues")

        return result


# 全局单例
_guard = StaticGuard()


def check_code(code: str) -> ScanResult:
    """便捷函数：使用默认策略扫描代码"""
    return _guard.check_code(code)
