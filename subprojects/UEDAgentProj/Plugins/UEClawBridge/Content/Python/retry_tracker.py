# -*- coding: utf-8 -*-
"""
retry_tracker.py - 工具调用重试追踪器
=====================================

追踪 MCP 工具调用的重试模式，自动检索记忆并提炼经验。

职责:
  - 追踪同类操作的连续失败
  - 连续失败 ≥2 次时自动搜索记忆
  - retry 后成功时提炼规则写入个人记忆
  - session reset 时清空状态

位置: core/retry_tracker.py (共享模块)
"""

import hashlib
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("artclaw.retry_tracker")


@dataclass
class CallRecord:
    """单次工具调用记录"""
    tool_name: str
    fingerprint: str     # 操作意图指纹
    is_error: bool
    error_snippet: str   # 错误信息前 200 字符
    code_snippet: str    # 代码前 300 字符
    result_snippet: str  # 结果前 200 字符
    timestamp: float = field(default_factory=time.time)


class RetryTracker:
    """追踪工具调用的重试模式
    
    通过操作指纹（提取代码中的 API 调用名）判断"同类操作"，
    当连续失败 ≥2 次时自动搜索记忆，retry 后成功时提炼规则。
    """

    # 连续失败多少次后触发记忆搜索
    SEARCH_THRESHOLD = 2
    # 记忆提示最大条数
    MAX_HINTS = 3
    # 每条提示最大字符数
    MAX_HINT_CHARS = 100
    # 操作历史保留的最大组数
    MAX_GROUPS = 50

    def __init__(self):
        # 按操作指纹分组的调用历史
        self._history: Dict[str, List[CallRecord]] = {}
        # 最近调用（用于 debug）
        self._recent: deque = deque(maxlen=100)
        # 记忆管理器引用（延迟绑定）
        self._memory_manager = None

    def set_memory_manager(self, mm):
        """绑定记忆管理器实例"""
        self._memory_manager = mm

    def clear(self):
        """清空所有追踪状态（新对话时调用）"""
        self._history.clear()
        self._recent.clear()
        logger.debug("RetryTracker 已清空")

    def on_tool_result(self, tool_name: str, code: str,
                       is_error: bool, error_msg: str,
                       result_text: str) -> Optional[str]:
        """记录工具调用结果，返回需要注入的记忆提示
        
        Args:
            tool_name: 工具名 (run_python / run_ue_python)
            code: 执行的代码
            is_error: 是否出错
            error_msg: 错误信息
            result_text: 执行结果文本
            
        Returns:
            None — 不需要注入
            str — 需要追加到 tool result 末尾的记忆提示
        """
        if not code.strip():
            return None

        fp = self._extract_fingerprint(tool_name, code)
        
        record = CallRecord(
            tool_name=tool_name,
            fingerprint=fp,
            is_error=is_error,
            error_snippet=error_msg[:200] if error_msg else "",
            code_snippet=code[:300],
            result_snippet=result_text[:200] if result_text else "",
        )
        
        self._history.setdefault(fp, []).append(record)
        self._recent.append(record)
        
        # 容量控制
        if len(self._history) > self.MAX_GROUPS:
            oldest_key = min(self._history, key=lambda k: self._history[k][-1].timestamp)
            del self._history[oldest_key]
        
        history = self._history[fp]
        consecutive_failures = self._count_consecutive_failures(history)
        
        # === 触发 1: 连续失败 ≥ N 次 → 自动查记忆 ===
        if is_error and consecutive_failures >= self.SEARCH_THRESHOLD:
            hints = self._search_memory_hints(code, error_msg)
            if hints:
                return hints
            # 没找到相关记忆时，给一个通用提示
            if consecutive_failures >= 3:
                return "[Memory] 连续失败 {}次，记忆中无相关规则。建议检查 API 文档或换个方案。".format(
                    consecutive_failures)
        
        # === 触发 2: retry 后成功 → 提炼规则写入记忆 ===
        if not is_error and len(history) >= 2:
            prev_failures = [r for r in history[:-1] if r.is_error]
            if prev_failures:
                self._extract_and_store_lesson(prev_failures, record)
                # 清空该指纹的历史（已学到教训）
                self._history[fp] = [record]
        
        return None

    # === 操作指纹 ===

    # 匹配 Python API 调用模式
    _API_PATTERN = re.compile(
        r'(?:unreal|cmds|mc|rt|pm|MaxPlus|pymxs|maya\.cmds|maya\.mel'
        r'|pymel\.core|om2?|OpenMaya)'
        r'\.\w+'
    )
    # 匹配 import 语句
    _IMPORT_PATTERN = re.compile(r'^\s*(?:from\s+(\S+)|import\s+(\S+))', re.MULTILINE)

    def _extract_fingerprint(self, tool_name: str, code: str) -> str:
        """提取操作意图指纹
        
        不能用完整代码 hash（每次 retry 代码都不同）。
        提取 API 调用名 + import 模块名，排序后 hash。
        """
        tokens = set()
        
        # 提取 API 调用
        for match in self._API_PATTERN.finditer(code):
            tokens.add(match.group())
        
        # 提取 import 模块
        for match in self._IMPORT_PATTERN.finditer(code):
            module = match.group(1) or match.group(2)
            if module:
                tokens.add(f"import:{module.split('.')[0]}")
        
        # 如果没提取到任何 token，用代码前 50 字符的 hash 兜底
        if not tokens:
            raw = code.strip()[:50]
            return hashlib.md5(f"{tool_name}:{raw}".encode()).hexdigest()[:12]
        
        fingerprint = f"{tool_name}:" + ",".join(sorted(tokens))
        return hashlib.md5(fingerprint.encode()).hexdigest()[:12]

    # === 连续失败计数 ===

    @staticmethod
    def _count_consecutive_failures(history: List[CallRecord]) -> int:
        """从最近的记录往前数，连续失败的次数"""
        count = 0
        for record in reversed(history):
            if record.is_error:
                count += 1
            else:
                break
        return count

    # === 记忆搜索 ===

    def _search_memory_hints(self, code: str, error_msg: str) -> Optional[str]:
        """从记忆中搜索相关提示"""
        mm = self._memory_manager
        if not mm:
            return None
        
        try:
            keywords = self._extract_search_keywords(code, error_msg)
            if not keywords:
                return None
            
            all_hints = []
            seen = set()
            
            for kw in keywords[:4]:
                # 搜索个人记忆
                for tag in ("crash", "pattern"):
                    results = mm.search(kw, tag=tag, limit=2)
                    for r in results:
                        hint = self._format_personal_hint(r)
                        if hint and hint not in seen:
                            all_hints.append(hint)
                            seen.add(hint)
                
                # 搜索团队记忆
                team_results = mm.search_team_memory(kw, limit=2)
                for rule in team_results:
                    short = rule[:self.MAX_HINT_CHARS]
                    if short not in seen:
                        all_hints.append(short)
                        seen.add(short)
                
                if len(all_hints) >= self.MAX_HINTS:
                    break
            
            if not all_hints:
                return None
            
            lines = [f"[Memory] ⚠ {h}" for h in all_hints[:self.MAX_HINTS]]
            return "\n".join(lines)
            
        except Exception as e:
            logger.debug(f"记忆搜索失败: {e}")
            return None

    @staticmethod
    def _extract_search_keywords(code: str, error_msg: str) -> List[str]:
        """从代码和错误信息中提取搜索关键词"""
        keywords = []
        
        # 从错误信息提取关键词
        if error_msg:
            # 提取 Python 异常类名
            exc_match = re.search(r'(\w+Error|\w+Exception|\w+Warning)', error_msg)
            if exc_match:
                keywords.append(exc_match.group(1))
            
            # 提取引号中的标识符
            for match in re.finditer(r"['\"](\w{3,30})['\"]", error_msg):
                keywords.append(match.group(1))
            
            # 错误信息前 30 字符
            clean = re.sub(r'[^\w\s]', ' ', error_msg[:60]).strip()
            if clean and len(clean) > 5:
                keywords.append(clean)
        
        # 从代码提取 API 名
        api_calls = re.findall(r'(?:unreal|cmds|rt)\.\w+', code)
        keywords.extend(api_calls[:3])
        
        # 去重保序
        seen = set()
        result = []
        for kw in keywords:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                result.append(kw)
        
        return result

    @staticmethod
    def _format_personal_hint(memory_entry: dict) -> Optional[str]:
        """将个人记忆条目格式化为简短提示"""
        value = memory_entry.get("value", "")
        
        if isinstance(value, dict):
            # crash 类型
            rule = value.get("avoidance_rule", "")
            if rule:
                return rule[:100]
            # pattern 类型
            fix = value.get("fix", "")
            if fix:
                return str(fix)[:100]
            return str(value)[:100]
        
        return str(value)[:100] if value else None

    # === 经验提炼 ===

    def _extract_and_store_lesson(self, failures: List[CallRecord],
                                  success: CallRecord):
        """从 失败→成功 的历史中提炼教训并写入记忆"""
        mm = self._memory_manager
        if not mm:
            return
        
        try:
            last_failure = failures[-1]
            retry_count = len(failures)
            
            # 构建教训内容
            lesson_value = {
                "error": last_failure.error_snippet,
                "failed_code": last_failure.code_snippet[:150],
                "success_code": success.code_snippet[:150],
                "retry_count": retry_count,
                "auto_extracted": True,
            }
            
            # 生成有意义的 key
            apis = self._API_PATTERN.findall(success.code_snippet)
            api_hint = apis[0] if apis else "unknown_op"
            lesson_key = f"pattern:{api_hint}:{int(time.time())}"
            
            # 重要性: retry 越多越重要 (0.6 基础 + 每次 retry +0.1，上限 0.95)
            importance = min(0.95, 0.6 + retry_count * 0.1)
            
            mm.record(
                key=lesson_key,
                value=lesson_value,
                tag="pattern",
                importance=importance,
                source="retry_tracker",
            )
            
            logger.info(f"RetryTracker 提炼教训: {lesson_key} (retry={retry_count}, "
                        f"importance={importance:.2f})")
            
        except Exception as e:
            logger.warning(f"RetryTracker 提炼教训失败: {e}")

    # === 统计 ===

    def get_stats(self) -> dict:
        """获取追踪器统计信息"""
        total_calls = len(self._recent)
        total_errors = sum(1 for r in self._recent if r.is_error)
        active_groups = len(self._history)
        
        # 找出当前有连续失败的组
        failing_groups = {}
        for fp, records in self._history.items():
            consecutive = self._count_consecutive_failures(records)
            if consecutive >= 1:
                failing_groups[fp] = {
                    "consecutive_failures": consecutive,
                    "last_error": records[-1].error_snippet[:60] if records[-1].is_error else "",
                    "tool": records[-1].tool_name,
                }
        
        return {
            "total_calls": total_calls,
            "total_errors": total_errors,
            "error_rate": total_errors / total_calls if total_calls > 0 else 0,
            "active_groups": active_groups,
            "failing_groups": failing_groups,
        }
