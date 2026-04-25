# -*- coding: utf-8 -*-
"""
ArtClaw Bridge 记忆管理系统 v2
平台无关的三级记忆模型实现

Author: ArtClaw Team  
Version: 2.0.0
"""

import json
import os
import time
import logging
import threading
import tempfile
import shutil
from typing import Any, Optional, List, Dict, Union
from difflib import SequenceMatcher
from copy import deepcopy

# 配置默认值
DEFAULT_CONFIG = {
    "short_term_ttl_hours": 4,
    "mid_term_ttl_days": 7,
    "short_term_max_entries": 200,
    "mid_term_max_entries": 500,
    "long_term_max_entries": 1000,
    "max_entry_size_bytes": 4096,
    "maintenance_interval_minutes": 30,
    "full_maintenance_interval_hours": 24,
    "auto_record_operations": True,
    "auto_record_crashes": True,
    "dedup_similarity_threshold": 0.8,
}

# 支持的语义标签
VALID_TAGS = {"fact", "preference", "convention", "operation", "crash", "pattern", "context"}

# 记忆层级
MEMORY_LAYERS = {"short_term", "mid_term", "long_term"}


class MemoryEntry:
    """记忆条目数据结构"""
    
    def __init__(self, key: str, value: Any, tag: str = "fact", importance: float = 0.5, 
                 source: str = "", expires_at: Optional[float] = None, promoted_from: Optional[str] = None):
        self.key = key
        self.value = value
        self.tag = tag if tag in VALID_TAGS else "fact"
        self.importance = max(0.0, min(1.0, importance))  # 限制在 0-1 范围
        self.source = source
        self.created_at = time.time()
        self.last_accessed = self.created_at
        self.access_count = 0
        self.expires_at = expires_at
        self.promoted_from = promoted_from
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "key": self.key,
            "value": self.value,
            "tag": self.tag,
            "importance": self.importance,
            "source": self.source,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "expires_at": self.expires_at,
            "promoted_from": self.promoted_from
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryEntry':
        """从字典创建条目"""
        entry = cls(
            key=data["key"],
            value=data["value"],
            tag=data.get("tag", "fact"),
            importance=data.get("importance", 0.5),
            source=data.get("source", ""),
            expires_at=data.get("expires_at"),
            promoted_from=data.get("promoted_from")
        )
        entry.created_at = data.get("created_at", time.time())
        entry.last_accessed = data.get("last_accessed", entry.created_at)
        entry.access_count = data.get("access_count", 0)
        return entry
    
    def update_access(self):
        """更新访问记录"""
        self.last_accessed = time.time()
        self.access_count += 1


class MemoryManagerV2:
    """ArtClaw 记忆管理器 v2"""
    
    def __init__(self, storage_path: str, dcc_name: str = "unknown", config: dict = None,
                 team_memory_path: str = ""):
        """初始化记忆管理器
        
        Args:
            storage_path: 存储文件路径
            dcc_name: DCC 软件名称标识
            config: 配置覆盖项
            team_memory_path: 团队记忆目录路径 (team_memory/)，为空则自动检测
        """
        self.storage_path = storage_path
        self.dcc_name = dcc_name
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
        # 团队记忆 (只读)
        self._team_memory_path = team_memory_path
        self._team_memory_cache: Dict[str, str] = {}  # filename -> content
        self._team_rule_hits: Dict[str, int] = {}  # rule_hash -> hit_count
        self._team_hits_path = ""  # 命中计数文件路径，_load_team_memory 后设置
        self._team_hits_dirty = False
        
        # 线程安全锁
        self._lock = threading.RLock()
        
        # 记忆存储
        self.short_term: Dict[str, MemoryEntry] = {}
        self.mid_term: Dict[str, MemoryEntry] = {}
        self.long_term: Dict[str, MemoryEntry] = {}
        
        # 元数据
        self._meta = {
            "version": "2.0.0",
            "dcc": dcc_name,
            "created": time.time(),
            "last_maintenance": 0,
            "last_save": 0,
            "stats": {
                "total_records": 0,
                "total_operations": 0,
                "total_crashes": 0,
                "promotions": {"short_to_mid": 0, "mid_to_long": 0},
                "cleanups": {"expired": 0, "capacity": 0, "dedup": 0}
            }
        }
        
        # 内存状态
        self._dirty = False
        self._last_save_time = 0
        
        # 定时维护
        self._maintenance_timer: Optional[threading.Timer] = None
        self._maintenance_running = False
        self._last_short_sweep = 0.0
        self._last_full_maintenance = 0.0
        
        # 日志配置
        self.logger = logging.getLogger("artclaw.memory")
        if not self.logger.handlers:
            # 优先使用 UE 原生 log（避免 Python stderr 被 UE 误标为 [Error]）
            try:
                import unreal as _unreal_log

                class _UELogHandler(logging.Handler):
                    _LEVEL_MAP = {
                        logging.DEBUG: _unreal_log.log,
                        logging.INFO: _unreal_log.log,
                        logging.WARNING: _unreal_log.log_warning,
                        logging.ERROR: _unreal_log.log_error,
                        logging.CRITICAL: _unreal_log.log_error,
                    }

                    def emit(self, record):
                        fn = self._LEVEL_MAP.get(record.levelno, _unreal_log.log)
                        try:
                            fn(self.format(record))
                        except Exception:
                            pass

                handler = _UELogHandler()
            except ImportError:
                # 非 UE 环境（Maya/Max/独立运行）回落到 stdout
                import sys as _sys
                handler = logging.StreamHandler(_sys.stdout)

            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # 加载现有数据
        self._load()
        
        # 加载团队记忆
        self._load_team_memory()
        
        # 检查上次是否异常退出（crash recovery）
        self._check_crash_recovery()
        
        self.logger.info(f"记忆管理器 v2 已初始化: {dcc_name}, 存储路径: {storage_path}")

    def _load(self):
        """加载记忆数据"""
        with self._lock:
            if not os.path.exists(self.storage_path):
                self.logger.info("存储文件不存在，将创建新的记忆库")
                return
            
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 加载元数据
                self._meta.update(data.get("_meta", {}))
                
                # 加载各层记忆
                for layer_name in MEMORY_LAYERS:
                    layer_data = data.get(layer_name, {})
                    layer_storage = getattr(self, layer_name)
                    
                    for key, entry_data in layer_data.items():
                        try:
                            entry = MemoryEntry.from_dict(entry_data)
                            layer_storage[key] = entry
                        except Exception as e:
                            self.logger.warning(f"跳过损坏的记忆条目 {key}: {e}")
                
                self.logger.info(f"已加载记忆数据: 短期{len(self.short_term)}, 中期{len(self.mid_term)}, 长期{len(self.long_term)}")
                
            except Exception as e:
                self.logger.error(f"加载记忆数据失败: {e}")
                # 备份损坏的文件
                backup_path = self.storage_path + ".corrupt.bak"
                try:
                    shutil.copy2(self.storage_path, backup_path)
                    self.logger.info(f"已备份损坏文件到: {backup_path}")
                except Exception as be:
                    self.logger.error(f"备份损坏文件失败: {be}")

    def _resolve_team_memory_path(self) -> str:
        """解析团队记忆目录路径
        
        优先级:
          1. 构造函数传入的 team_memory_path
          2. config.json 的 project_root + /team_memory/
          3. 空字符串（不加载）
        """
        if self._team_memory_path and os.path.isdir(self._team_memory_path):
            return self._team_memory_path
        
        # 从 config.json 读取 project_root
        try:
            config_path = os.path.join(os.path.expanduser("~"), ".artclaw", "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                project_root = cfg.get("project_root", "")
                if project_root:
                    candidate = os.path.join(project_root, "team_memory")
                    if os.path.isdir(candidate):
                        return candidate
        except Exception:
            pass
        
        return ""

    # 每个团队记忆文件的规则条数上限
    _TEAM_MEMORY_LIMITS = {
        "crash_rules.md": 15,
        "gotchas.md": 20,
        "conventions.md": 10,
        "platform_differences.md": 8,
    }

    def _load_team_memory(self):
        """加载团队记忆文件 (只读 Markdown)
        
        处理流程:
          1. 按当前 DCC 过滤规则 (只加载 [All] 和 [当前DCC] 标签)
          2. 语义去重 (SequenceMatcher > 0.75 视为重复)
          3. 取最后 N 条 (新规则追加在文件末尾，最新的优先保留)
          4. 反转为最新在前的顺序
        """
        team_dir = self._resolve_team_memory_path()
        if not team_dir:
            return
        
        # DCC 名称到标签的映射
        dcc_lower = self.dcc_name.lower()
        _DCC_TAG_MAP = {
            "ue": ["[UE]", "[All]"],
            "unreal": ["[UE]", "[All]"],
            "maya": ["[Maya]", "[All]"],
            "3dsmax": ["[Max]", "[All]"],
            "max": ["[Max]", "[All]"],
        }
        allowed_tags = _DCC_TAG_MAP.get(dcc_lower, ["[All]"])
        filter_by_dcc = dcc_lower in _DCC_TAG_MAP
        all_dcc_tags = ["[UE]", "[Maya]", "[Max]", "[All]", "[Python]", "[Windows]"]
        universal_tags = ["[Python]", "[Windows]"]
        
        loaded = 0
        for fname, max_rules in self._TEAM_MEMORY_LIMITS.items():
            fpath = os.path.join(team_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Step 1: 提取规则行 + DCC 过滤
                raw_rules = []
                for line in content.split("\n"):
                    stripped = line.strip()
                    if not stripped.startswith("- "):
                        continue
                    rule_text = stripped[2:]
                    if filter_by_dcc:
                        has_tag = any(tag in rule_text for tag in all_dcc_tags)
                        if has_tag and not any(tag in rule_text for tag in allowed_tags + universal_tags):
                            continue
                    raw_rules.append(rule_text)
                
                if not raw_rules:
                    continue
                
                # Step 2: 语义去重 (保留后出现的版本，因为更新)
                deduped = self._dedup_rules(raw_rules)
                
                # Step 3: 取最后 N 条 (最新的优先)
                if len(deduped) > max_rules:
                    deduped = deduped[-max_rules:]
                
                # Step 4: 反转为最新在前
                deduped.reverse()
                
                self._team_memory_cache[fname] = deduped
                loaded += len(deduped)
                
            except Exception as e:
                self.logger.warning(f"加载团队记忆失败 {fname}: {e}")
        
        if loaded:
            self.logger.info(f"已加载团队记忆: {loaded} 条规则 (DCC={self.dcc_name}) from {team_dir}")
        
        self._team_memory_path = team_dir
        
        # 加载命中计数
        self._load_team_hits(team_dir)

    @staticmethod
    def _dedup_rules(rules: List[str], threshold: float = 0.75) -> List[str]:
        """对规则列表做语义去重
        
        相似度 > threshold 的规则只保留后出现的版本（更新的覆盖旧的）。
        使用 SequenceMatcher 比较去掉标签后的纯文本。
        """
        if len(rules) <= 1:
            return rules
        
        import re
        tag_pattern = re.compile(r'\[(?:UE|Maya|Max|All|Python|Windows)\]\s*')
        
        def strip_tags(text: str) -> str:
            return tag_pattern.sub('', text).strip().lower()
        
        # 从后往前扫描，后出现的优先保留
        kept = []
        kept_texts = []
        for rule in reversed(rules):
            clean = strip_tags(rule)
            is_dup = False
            for existing in kept_texts:
                if SequenceMatcher(None, clean, existing).ratio() > threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(rule)
                kept_texts.append(clean)
        
        kept.reverse()  # 恢复原始顺序
        return kept

    def _load_team_hits(self, team_dir: str):
        """加载团队规则命中计数"""
        # 存储在个人目录（不同用户各自的计数）
        storage_dir = os.path.dirname(self.storage_path)
        self._team_hits_path = os.path.join(storage_dir, "team_hits.json")
        
        if os.path.isfile(self._team_hits_path):
            try:
                with open(self._team_hits_path, "r", encoding="utf-8") as f:
                    self._team_rule_hits = json.load(f)
                self.logger.debug(f"已加载团队规则命中计数: {len(self._team_rule_hits)} 条")
            except Exception:
                self._team_rule_hits = {}

    def _save_team_hits(self):
        """保存团队规则命中计数"""
        if not self._team_hits_dirty or not self._team_hits_path:
            return
        try:
            os.makedirs(os.path.dirname(self._team_hits_path), exist_ok=True)
            with open(self._team_hits_path, "w", encoding="utf-8") as f:
                json.dump(self._team_rule_hits, f, ensure_ascii=False)
            self._team_hits_dirty = False
        except Exception as e:
            self.logger.warning(f"保存团队命中计数失败: {e}")

    @staticmethod
    def _rule_hash(rule: str) -> str:
        """生成规则的短 hash 作为计数 key"""
        import hashlib
        return hashlib.md5(rule.strip().lower().encode("utf-8")).hexdigest()[:12]

    def _record_team_hits(self, rules: List[str]):
        """记录被命中的规则"""
        for rule in rules:
            h = self._rule_hash(rule)
            self._team_rule_hits[h] = self._team_rule_hits.get(h, 0) + 1
            self._team_hits_dirty = True

    def _get_team_hit_count(self, rule: str) -> int:
        """获取规则的命中次数"""
        return self._team_rule_hits.get(self._rule_hash(rule), 0)

    def search_team_memory(self, query: str, limit: int = 3) -> List[str]:
        """搜索团队记忆中的相关规则
        
        命中的规则自动 +1 计数，用于排序优化。
        
        Args:
            query: 搜索关键词
            limit: 最大返回条数
            
        Returns:
            匹配的规则文本列表
        """
        if not self._team_memory_cache:
            return []
        
        query_lower = query.lower()
        results = []
        
        # 优先搜索 crash_rules 和 gotchas
        priority_order = ["crash_rules.md", "gotchas.md", "conventions.md", "platform_differences.md"]
        
        for fname in priority_order:
            rules = self._team_memory_cache.get(fname, [])
            for rule in rules:
                if query_lower in rule.lower():
                    results.append(rule)
                    if len(results) >= limit:
                        break
            if len(results) >= limit:
                break
        
        # 记录命中
        if results:
            self._record_team_hits(results)
            self._save_team_hits()
        
        return results

    # === 团队记忆写入 ===

    # 规则类型到目标文件的映射
    _TEAM_FILE_MAP = {
        "crash": "crash_rules.md",
        "gotcha": "gotchas.md",
        "pattern": "gotchas.md",
        "convention": "conventions.md",
        "platform": "platform_differences.md",
    }

    def propose_team_rule(self, rule_text: str, category: str = "gotcha",
                          dcc_tag: str = "") -> dict:
        """提议一条新的团队记忆规则
        
        检查是否与已有规则重复，如果不重复则追加到对应文件。
        
        Args:
            rule_text: 规则内容（不含 "- " 前缀和 DCC 标签）
            category: 规则类别 (crash/gotcha/pattern/convention/platform)
            dcc_tag: DCC 标签，如 "[UE]"、"[Maya]"、"[All]"，为空则不加标签
            
        Returns:
            {"accepted": bool, "reason": str, "file": str}
        """
        team_dir = self._resolve_team_memory_path()
        if not team_dir:
            return {"accepted": False, "reason": "team_memory 目录未找到", "file": ""}
        
        target_file = self._TEAM_FILE_MAP.get(category, "gotchas.md")
        fpath = os.path.join(team_dir, target_file)
        
        # 构建完整规则行
        if dcc_tag and not dcc_tag.startswith("["):
            dcc_tag = f"[{dcc_tag}]"
        full_rule = f"{dcc_tag} {rule_text}".strip() if dcc_tag else rule_text.strip()
        
        # 检查与已有规则的重复
        existing_rules = self._team_memory_cache.get(target_file, [])
        # 也读取文件中未被 DCC 过滤的全部规则（缓存可能只有当前 DCC 的子集）
        all_file_rules = self._read_all_rules_from_file(fpath)
        
        import re
        tag_pattern = re.compile(r'\[(?:UE|Maya|Max|All|Python|Windows)\]\s*')
        clean_new = tag_pattern.sub('', full_rule).strip().lower()
        
        for existing in all_file_rules:
            clean_old = tag_pattern.sub('', existing).strip().lower()
            if SequenceMatcher(None, clean_new, clean_old).ratio() > 0.75:
                return {
                    "accepted": False,
                    "reason": f"与已有规则重复: {existing[:60]}...",
                    "file": target_file,
                }
        
        # 追加到文件末尾
        try:
            with open(fpath, "a", encoding="utf-8") as f:
                f.write(f"\n- {full_rule}")
            
            # 更新缓存
            if target_file not in self._team_memory_cache:
                self._team_memory_cache[target_file] = []
            self._team_memory_cache[target_file].append(full_rule)
            
            self.logger.info(f"团队记忆新增: [{category}] {full_rule[:60]}")
            return {
                "accepted": True,
                "reason": "已追加到团队记忆",
                "file": target_file,
            }
        except Exception as e:
            self.logger.error(f"写入团队记忆失败: {e}")
            return {"accepted": False, "reason": f"写入失败: {e}", "file": target_file}

    @staticmethod
    def _read_all_rules_from_file(fpath: str) -> List[str]:
        """从文件中读取全部规则行（不做 DCC 过滤）"""
        if not os.path.isfile(fpath):
            return []
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.read().split("\n")
            return [line.strip()[2:] for line in lines if line.strip().startswith("- ")]
        except Exception:
            return []

    def promote_to_team(self, min_importance: float = 0.7,
                        tags: tuple = ("crash", "pattern", "convention"),
                        dry_run: bool = True) -> List[dict]:
        """从个人记忆中筛选高价值条目，提炼为团队规则
        
        Args:
            min_importance: 最低重要性阈值
            tags: 要扫描的标签
            dry_run: True=只返回候选列表不写入, False=实际写入
            
        Returns:
            候选/写入结果列表 [{"key": str, "rule": str, "category": str, "result": dict}]
        """
        candidates = []
        
        # 从 long_term 和 mid_term 中筛选
        for layer_name in ["long_term", "mid_term"]:
            layer_storage = self._get_layer_by_name(layer_name)
            for key, entry in layer_storage.items():
                if entry.tag not in tags:
                    continue
                if entry.importance < min_importance:
                    continue
                
                # 提炼规则文本
                rule_text = self._extract_rule_text(entry)
                if not rule_text:
                    continue
                
                # 推断 DCC 标签
                dcc_tag = self._infer_dcc_tag(entry)
                
                # 推断类别
                category = "crash" if entry.tag == "crash" else (
                    "convention" if entry.tag == "convention" else "gotcha"
                )
                
                candidate = {
                    "key": key,
                    "rule": rule_text,
                    "dcc_tag": dcc_tag,
                    "category": category,
                    "importance": entry.importance,
                }
                
                if not dry_run:
                    result = self.propose_team_rule(rule_text, category, dcc_tag)
                    candidate["result"] = result
                
                candidates.append(candidate)
        
        return candidates

    @staticmethod
    def _extract_rule_text(entry: 'MemoryEntry') -> str:
        """从记忆条目中提取精简规则文本"""
        value = entry.value
        
        if isinstance(value, dict):
            # crash 类型: 优先 avoidance_rule, 否则从 error 生成
            if entry.tag == "crash":
                rule = value.get("avoidance_rule", "").strip()
                if rule:
                    tool = value.get("tool", "")
                    return f"{tool}: {rule}" if tool else rule
                # fallback: 从 error 信息生成简短规则
                error = value.get("error", "").strip()
                tool = value.get("tool", "")
                action = value.get("action", "")
                if error:
                    short_error = error.split("\n")[-1].strip()[:100] if "\n" in error else error[:100]
                    parts = [p for p in [tool, action, short_error] if p]
                    return " → ".join(parts) if parts else ""
            # pattern 类型 (RetryTracker 自动提取的)
            if entry.tag == "pattern":
                # 有 fix 字段直接用
                if "fix" in value:
                    return str(value["fix"])[:100]
                # RetryTracker 格式: error + success_code
                error_part = value.get("error", "")
                success_part = value.get("success_code", "")
                if error_part and success_part:
                    return f"错误 '{error_part[:50]}' → 正确做法: {success_part[:80]}"
                if error_part:
                    return f"避免: {error_part[:100]}"
            # operation summary
            if value.get("type") == "operation_summary":
                return ""  # 操作摘要不适合提炼为规则
            # 通用 dict
            return str(value)[:100]
        
        return str(value)[:100] if value else ""

    @staticmethod
    def _infer_dcc_tag(entry: 'MemoryEntry') -> str:
        """从记忆条目推断 DCC 标签"""
        source = entry.source.lower()
        key = entry.key.lower()
        text = str(entry.value).lower()
        combined = f"{source} {key} {text}"
        
        if "unreal" in combined or "ue" in combined or "slate" in combined:
            return "[UE]"
        if "maya" in combined or "cmds" in combined:
            return "[Maya]"
        if "max" in combined or "pymxs" in combined:
            return "[Max]"
        return "[All]"

    def _save(self):
        """保存记忆数据到磁盘"""
        # 频率控制：距离上次保存少于5秒则跳过
        current_time = time.time()
        if current_time - self._last_save_time < 5:
            self._dirty = True
            return
        
        with self._lock:
            try:
                # 构建保存数据
                save_data = {
                    "_meta": self._meta.copy(),
                    "short_term": {k: v.to_dict() for k, v in self.short_term.items()},
                    "mid_term": {k: v.to_dict() for k, v in self.mid_term.items()},
                    "long_term": {k: v.to_dict() for k, v in self.long_term.items()}
                }
                
                # 更新元数据
                save_data["_meta"]["last_save"] = current_time
                save_data["_meta"]["stats"]["total_records"] = (
                    len(self.short_term) + len(self.mid_term) + len(self.long_term)
                )
                
                # 原子性写入：先写临时文件，再重命名
                temp_path = self.storage_path + ".tmp"
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
                
                # 重命名到目标文件
                if os.path.exists(self.storage_path):
                    backup_path = self.storage_path + ".bak"
                    shutil.copy2(self.storage_path, backup_path)
                
                shutil.move(temp_path, self.storage_path)
                
                self._last_save_time = current_time
                self._dirty = False
                self._meta["last_save"] = current_time
                
                self.logger.debug("记忆数据已保存")
                
            except Exception as e:
                self.logger.error(f"保存记忆数据失败: {e}")
                # 清理临时文件
                temp_path = self.storage_path + ".tmp"
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

    def _mark_dirty(self):
        """标记数据已修改"""
        self._dirty = True

    def flush(self):
        """强制将所有未保存的数据写入磁盘（关闭/退出时调用）"""
        if self._dirty:
            self._last_save_time = 0  # 重置频率控制，确保写入
            self._save()
        self._save_team_hits()

    def start_maintenance_timer(self):
        """启动定时维护后台线程

        每隔 maintenance_interval_minutes 分钟执行一次短期扫描，
        每隔 full_maintenance_interval_hours 小时执行一次完整维护。
        """
        if self._maintenance_running:
            return

        self._maintenance_running = True
        interval_sec = self.config["maintenance_interval_minutes"] * 60

        def _tick():
            if not self._maintenance_running:
                return
            try:
                now = time.time()
                short_interval = self.config["maintenance_interval_minutes"] * 60
                full_interval = self.config["full_maintenance_interval_hours"] * 3600

                # 判断是否需要完整维护
                do_full = (now - self._last_full_maintenance) >= full_interval

                if do_full:
                    self.maintain(full=True)
                    self._last_full_maintenance = now
                    self._last_short_sweep = now
                elif (now - self._last_short_sweep) >= short_interval:
                    self.maintain(full=False)
                    self._last_short_sweep = now

                # 顺便保存 dirty 数据
                if self._dirty:
                    self._last_save_time = 0
                    self._save()

            except Exception as e:
                self.logger.error(f"定时维护出错: {e}")
            finally:
                # 重新调度
                if self._maintenance_running:
                    self._maintenance_timer = threading.Timer(interval_sec, _tick)
                    self._maintenance_timer.daemon = True
                    self._maintenance_timer.start()

        self._maintenance_timer = threading.Timer(interval_sec, _tick)
        self._maintenance_timer.daemon = True
        self._maintenance_timer.start()
        self.logger.info(f"定时维护已启动: 短期扫描每 {self.config['maintenance_interval_minutes']} 分钟, "
                        f"完整维护每 {self.config['full_maintenance_interval_hours']} 小时")

    def stop_maintenance_timer(self):
        """停止定时维护"""
        self._maintenance_running = False
        if self._maintenance_timer:
            self._maintenance_timer.cancel()
            self._maintenance_timer = None
            self.logger.info("定时维护已停止")

        # 关闭时强制保存
        self.flush()
        # 清除执行哨兵（正常关闭标记）
        self.clear_execution_sentinel()

    # === Crash Recovery Sentinel ===

    def _sentinel_path(self) -> str:
        """获取执行哨兵文件路径"""
        return self.storage_path + ".running"

    def write_execution_sentinel(self, code_snippet: str, tool_name: str = ""):
        """在执行代码前写入哨兵文件
        
        如果 DCC 进程崩溃，哨兵文件不会被清除，
        下次启动时 _check_crash_recovery() 会检测到并记录。
        """
        try:
            sentinel = {
                "tool": tool_name,
                "code": code_snippet[:500],
                "timestamp": time.time(),
                "dcc": self.dcc_name,
            }
            with open(self._sentinel_path(), "w", encoding="utf-8") as f:
                json.dump(sentinel, f, ensure_ascii=False)
        except Exception:
            pass  # 哨兵写入失败不影响正常执行

    def clear_execution_sentinel(self):
        """执行成功后清除哨兵（包括正常关闭时调用）"""
        try:
            p = self._sentinel_path()
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    def _check_crash_recovery(self):
        """启动时检查是否存在上次异常退出的哨兵文件
        
        如果存在，说明上次执行的代码导致了进程崩溃，
        自动记录到 crash 记忆中。
        """
        sentinel_file = self._sentinel_path()
        if not os.path.exists(sentinel_file):
            return
        
        try:
            with open(sentinel_file, "r", encoding="utf-8") as f:
                sentinel = json.load(f)
            
            tool = sentinel.get("tool", "unknown")
            code = sentinel.get("code", "")
            ts = sentinel.get("timestamp", 0)
            
            # 计算距离崩溃的时间
            elapsed = time.time() - ts if ts else 0
            elapsed_str = f"{elapsed / 3600:.1f}h ago" if elapsed > 3600 else f"{elapsed / 60:.0f}min ago"
            
            self.logger.warning(
                f"检测到上次异常退出 ({elapsed_str}): "
                f"tool={tool}, code={code[:80]}..."
            )
            
            # 记录到 crash 记忆
            self.record_crash(
                tool=tool,
                action=code[:60].replace("\n", " "),
                params_summary=f"crash_recovery, {elapsed_str}",
                error="DCC 进程异常退出（哨兵文件未被清除）",
                root_cause="",
                avoidance_rule="",
                severity="high",
            )
            
            # 清除哨兵
            os.remove(sentinel_file)
            
        except Exception as e:
            self.logger.error(f"Crash recovery 检测失败: {e}")
            # 尝试清除损坏的哨兵
            try:
                os.remove(sentinel_file)
            except Exception:
                pass

    def _get_layer_by_name(self, layer: str) -> Dict[str, MemoryEntry]:
        """根据名称获取存储层"""
        if layer == "short_term":
            return self.short_term
        elif layer == "mid_term":
            return self.mid_term
        elif layer == "long_term":
            return self.long_term
        else:
            raise ValueError(f"无效的记忆层级: {layer}")

    def _calculate_expires_at(self, layer: str) -> Optional[float]:
        """计算过期时间"""
        current_time = time.time()
        if layer == "short_term":
            return current_time + (self.config["short_term_ttl_hours"] * 3600)
        elif layer == "mid_term":
            return current_time + (self.config["mid_term_ttl_days"] * 24 * 3600)
        else:  # long_term
            return None

    # === 基本 CRUD 操作 ===
    
    def record(self, key: str, value: Any, tag: str = "fact", importance: float = 0.5, source: str = "") -> bool:
        """记录新的记忆到短期存储
        
        Args:
            key: 记忆键名
            value: 记忆内容
            tag: 语义标签
            importance: 重要性评分 (0-1)
            source: 来源标识
            
        Returns:
            是否记录成功
        """
        with self._lock:
            try:
                # 验证参数
                if not key or not isinstance(key, str):
                    self.logger.error("记忆键名无效")
                    return False
                
                if tag not in VALID_TAGS:
                    self.logger.warning(f"无效的标签 {tag}，使用默认标签 'fact'")
                    tag = "fact"
                
                # 检查大小限制
                try:
                    value_size = len(json.dumps(value, default=str))
                    if value_size > self.config["max_entry_size_bytes"]:
                        self.logger.warning(f"记忆内容过大 ({value_size} bytes)，截断处理")
                        value = str(value)[:self.config["max_entry_size_bytes"] // 4] + "..."
                except:
                    value = str(value)[:1000]  # 强制截断
                
                # 创建记忆条目
                expires_at = self._calculate_expires_at("short_term")
                entry = MemoryEntry(
                    key=key, 
                    value=value, 
                    tag=tag, 
                    importance=importance, 
                    source=source,
                    expires_at=expires_at
                )
                
                # 检查是否存在同样的key，如果存在则更新
                if key in self.short_term:
                    old_entry = self.short_term[key]
                    entry.access_count = old_entry.access_count
                    entry.created_at = old_entry.created_at
                
                self.short_term[key] = entry
                self._mark_dirty()
                
                # 检查容量限制
                if len(self.short_term) > self.config["short_term_max_entries"]:
                    self._run_short_term_sweep()
                
                self._save()
                self.logger.debug(f"已记录短期记忆: {key} [{tag}]")
                return True
                
            except Exception as e:
                self.logger.error(f"记录记忆失败: {e}")
                return False

    def get(self, key: str, layer: str = None) -> Optional[dict]:
        """获取记忆条目
        
        Args:
            key: 记忆键名
            layer: 指定层级，None表示跨层搜索
            
        Returns:
            记忆条目字典，未找到返回None
        """
        with self._lock:
            try:
                # 搜索顺序：先短期，再中期，最后长期
                search_layers = [layer] if layer else ["short_term", "mid_term", "long_term"]
                
                for layer_name in search_layers:
                    if layer_name not in MEMORY_LAYERS:
                        continue
                        
                    layer_storage = self._get_layer_by_name(layer_name)
                    if key in layer_storage:
                        entry = layer_storage[key]
                        
                        # 检查是否过期
                        if entry.expires_at and time.time() > entry.expires_at:
                            self.logger.debug(f"记忆已过期，自动删除: {key}")
                            del layer_storage[key]
                            self._mark_dirty()
                            continue
                        
                        # 更新访问记录
                        entry.update_access()
                        self._mark_dirty()
                        
                        result = entry.to_dict()
                        result["layer"] = layer_name
                        return result
                
                return None
                
            except Exception as e:
                self.logger.error(f"获取记忆失败 {key}: {e}")
                return None

    def delete(self, key: str, layer: str = None) -> bool:
        """删除记忆条目
        
        Args:
            key: 记忆键名
            layer: 指定层级，None表示跨层删除
            
        Returns:
            是否删除成功
        """
        with self._lock:
            try:
                deleted = False
                search_layers = [layer] if layer else ["short_term", "mid_term", "long_term"]
                
                for layer_name in search_layers:
                    if layer_name not in MEMORY_LAYERS:
                        continue
                        
                    layer_storage = self._get_layer_by_name(layer_name)
                    if key in layer_storage:
                        del layer_storage[key]
                        deleted = True
                        self.logger.debug(f"已删除记忆: {key} from {layer_name}")
                
                if deleted:
                    self._mark_dirty()
                    self._save()
                    return True
                else:
                    self.logger.warning(f"未找到要删除的记忆: {key}")
                    return False
                
            except Exception as e:
                self.logger.error(f"删除记忆失败 {key}: {e}")
                return False

    def search(self, query: str, tag: str = None, layer: str = None, limit: int = 10) -> List[dict]:
        """搜索记忆条目
        
        Args:
            query: 搜索关键词
            tag: 标签过滤
            layer: 层级过滤
            limit: 结果数量限制
            
        Returns:
            匹配的记忆条目列表
        """
        with self._lock:
            try:
                results = []
                search_layers = [layer] if layer else ["short_term", "mid_term", "long_term"]
                query_lower = query.lower() if query else ""
                
                for layer_name in search_layers:
                    if layer_name not in MEMORY_LAYERS:
                        continue
                        
                    layer_storage = self._get_layer_by_name(layer_name)
                    
                    for key, entry in layer_storage.items():
                        # 检查是否过期
                        if entry.expires_at and time.time() > entry.expires_at:
                            continue
                        
                        # 标签过滤
                        if tag and entry.tag != tag:
                            continue
                        
                        # 关键词匹配
                        if query:
                            key_match = query_lower in key.lower()
                            value_match = query_lower in str(entry.value).lower()
                            source_match = query_lower in entry.source.lower()
                            
                            if not (key_match or value_match or source_match):
                                continue
                        
                        result = entry.to_dict()
                        result["layer"] = layer_name
                        results.append(result)
                        
                        if len(results) >= limit:
                            break
                    
                    if len(results) >= limit:
                        break
                
                # 按重要性和访问频次排序
                results.sort(key=lambda x: (x["importance"] * 0.7 + (x["access_count"] / 10) * 0.3), reverse=True)
                
                return results[:limit]
                
            except Exception as e:
                self.logger.error(f"搜索记忆失败: {e}")
                return []

    def list_entries(self, layer: str = None, tag: str = None, limit: int = 50) -> List[dict]:
        """列出记忆条目
        
        Args:
            layer: 层级过滤
            tag: 标签过滤
            limit: 结果数量限制
            
        Returns:
            记忆条目列表
        """
        with self._lock:
            try:
                results = []
                search_layers = [layer] if layer else ["short_term", "mid_term", "long_term"]
                
                for layer_name in search_layers:
                    if layer_name not in MEMORY_LAYERS:
                        continue
                        
                    layer_storage = self._get_layer_by_name(layer_name)
                    
                    for key, entry in layer_storage.items():
                        # 检查是否过期
                        if entry.expires_at and time.time() > entry.expires_at:
                            continue
                        
                        # 标签过滤
                        if tag and entry.tag != tag:
                            continue
                        
                        result = entry.to_dict()
                        result["layer"] = layer_name
                        results.append(result)
                        
                        if len(results) >= limit:
                            break
                    
                    if len(results) >= limit:
                        break
                
                # 按最近访问时间排序
                results.sort(key=lambda x: x["last_accessed"], reverse=True)
                
                return results[:limit]
                
            except Exception as e:
                self.logger.error(f"列出记忆失败: {e}")
                return []

    # === 操作链路记录 ===
    
    def record_operation(self, tool: str, action: str, params_summary: str, result: str, 
                        duration_ms: int = 0, error: str = "", notes: str = "") -> None:
        """记录操作执行信息
        
        Args:
            tool: 工具名称
            action: 操作动作
            params_summary: 参数摘要
            result: 执行结果
            duration_ms: 执行时长(毫秒)
            error: 错误信息
            notes: 备注信息
        """
        if not self.config["auto_record_operations"]:
            return
            
        try:
            # 构建操作记录
            success = bool(error == "")
            operation_key = f"operation:{tool}:{action}"
            
            operation_data = {
                "tool": tool,
                "action": action, 
                "params": params_summary,
                "result": result[:500],  # 限制结果长度
                "success": success,
                "duration_ms": duration_ms,
                "error": error[:200] if error else "",
                "notes": notes[:200] if notes else "",
                "timestamp": time.time()
            }
            
            # 计算重要性：成功的操作基础0.3，失败的0.7
            importance = 0.7 if error else 0.3
            if duration_ms > 5000:  # 耗时操作更重要
                importance += 0.1
            
            self.record(
                key=operation_key,
                value=operation_data,
                tag="operation",
                importance=min(1.0, importance),
                source=f"{tool}.{action}"
            )
            
            self._meta["stats"]["total_operations"] += 1
            self.logger.debug(f"已记录操作: {tool}.{action} ({'成功' if success else '失败'})")
            
        except Exception as e:
            self.logger.error(f"记录操作失败: {e}")

    def record_crash(self, tool: str, action: str, params_summary: str, error: str,
                    root_cause: str, avoidance_rule: str, severity: str = "high") -> None:
        """记录崩溃信息
        
        Args:
            tool: 工具名称
            action: 操作动作
            params_summary: 参数摘要
            error: 错误信息
            root_cause: 根本原因分析
            avoidance_rule: 避免规则
            severity: 严重程度 (low/medium/high/critical)
        """
        if not self.config["auto_record_crashes"]:
            return
            
        try:
            crash_key = f"crash:{tool}:{action}:{int(time.time())}"
            
            crash_data = {
                "tool": tool,
                "action": action,
                "params": params_summary,
                "error": error[:500],
                "root_cause": root_cause,
                "avoidance_rule": avoidance_rule,
                "severity": severity,
                "timestamp": time.time()
            }
            
            # 崩溃记录都是高重要性
            severity_importance = {
                "low": 0.6,
                "medium": 0.7, 
                "high": 0.8,
                "critical": 0.9
            }
            importance = severity_importance.get(severity, 0.8)
            
            self.record(
                key=crash_key,
                value=crash_data,
                tag="crash",
                importance=importance,
                source=f"{tool}.crash"
            )
            
            self._meta["stats"]["total_crashes"] += 1
            self.logger.warning(f"已记录崩溃: {tool}.{action} [{severity}]")
            
        except Exception as e:
            self.logger.error(f"记录崩溃失败: {e}")

    def check_operation(self, tool: str, action_hint: str = "") -> dict:
        """检查操作历史记录
        
        Args:
            tool: 工具名称
            action_hint: 动作提示（用于模糊匹配）
            
        Returns:
            包含成功率、崩溃记录、建议的字典
        """
        try:
            # 搜索相关操作记录
            operation_results = self.search(f"operation:{tool}", tag="operation", limit=50)
            crash_results = self.search(f"crash:{tool}", tag="crash", limit=20)
            
            # 如果有action_hint，进一步过滤
            if action_hint:
                operation_results = [r for r in operation_results if action_hint.lower() in r["key"].lower()]
                crash_results = [r for r in crash_results if action_hint.lower() in r["key"].lower()]
            
            # 统计成功率
            total_ops = len(operation_results)
            success_ops = sum(1 for r in operation_results if r["value"].get("success", False))
            success_rate = (success_ops / total_ops) if total_ops > 0 else 0
            
            # 收集崩溃规则
            crash_rules = []
            for crash in crash_results[:5]:  # 最近5个崩溃
                crash_data = crash["value"]
                rule = crash_data.get("avoidance_rule", "")
                if rule and rule not in crash_rules:
                    crash_rules.append(rule)
            
            # 生成建议
            suggestions = []
            if success_rate < 0.5:
                suggestions.append("此操作失败率较高，建议谨慎使用")
            if len(crash_results) > 0:
                suggestions.append("存在崩溃记录，请参考避免规则")
            if total_ops == 0:
                suggestions.append("无操作历史，首次使用请小心")
            
            return {
                "tool": tool,
                "action_hint": action_hint,
                "total_operations": total_ops,
                "success_rate": success_rate,
                "crash_count": len(crash_results),
                "crash_rules": crash_rules,
                "suggestions": suggestions,
                "recent_errors": [r["value"].get("error", "") for r in operation_results[-3:] if not r["value"].get("success", True)]
            }
            
        except Exception as e:
            self.logger.error(f"检查操作历史失败: {e}")
            return {
                "tool": tool,
                "action_hint": action_hint,
                "error": str(e),
                "suggestions": ["检查操作历史时出错"]
            }

    # === 维护功能 ===
    
    def maintain(self, full: bool = False) -> dict:
        """执行记忆维护
        
        Args:
            full: 是否执行完整维护
            
        Returns:
            维护统计信息
        """
        with self._lock:
            start_time = time.time()
            stats = {
                "duration_ms": 0,
                "short_term_promotions": 0,
                "mid_term_promotions": 0,
                "expired_cleaned": 0,
                "capacity_cleaned": 0,
                "deduplicated": 0,
                "errors": []
            }
            
            try:
                self.logger.info(f"开始记忆维护 ({'完整' if full else '常规'})")
                
                # 1. 短期记忆扫描和晋升
                short_stats = self._run_short_term_sweep()
                stats["short_term_promotions"] = short_stats.get("promoted", 0)
                stats["expired_cleaned"] += short_stats.get("expired", 0)
                
                # 2. 中期记忆扫描和晋升
                mid_stats = self._run_mid_term_sweep()
                stats["mid_term_promotions"] = mid_stats.get("promoted", 0)
                stats["expired_cleaned"] += mid_stats.get("expired", 0)
                
                # 3. 容量检查和清理
                capacity_stats = self._run_capacity_check()
                stats["capacity_cleaned"] = capacity_stats.get("cleaned", 0)
                
                # 4. 完整维护额外操作
                if full:
                    # 去重
                    dedup_stats = self._run_dedup()
                    stats["deduplicated"] = dedup_stats.get("merged", 0)
                
                # 5. 保存数据
                if self._dirty:
                    self._save()
                
                # 更新维护时间
                self._meta["last_maintenance"] = time.time()
                
                stats["duration_ms"] = int((time.time() - start_time) * 1000)
                
                self.logger.info(f"记忆维护完成: 用时{stats['duration_ms']}ms, "
                               f"短期晋升{stats['short_term_promotions']}, "
                               f"中期晋升{stats['mid_term_promotions']}, "
                               f"清理{stats['expired_cleaned'] + stats['capacity_cleaned']}")
                
                return stats
                
            except Exception as e:
                self.logger.error(f"记忆维护失败: {e}")
                stats["errors"].append(str(e))
                stats["duration_ms"] = int((time.time() - start_time) * 1000)
                return stats

    def _run_short_term_sweep(self) -> dict:
        """短期记忆扫描和晋升"""
        try:
            current_time = time.time()
            promoted = 0
            expired = 0
            to_remove = []
            to_promote = []
            
            for key, entry in self.short_term.items():
                # 检查是否过期
                if entry.expires_at and current_time > entry.expires_at:
                    # 根据规则决定是否晋升
                    if self._should_promote_to_mid(entry):
                        to_promote.append((key, entry))
                    else:
                        to_remove.append(key)
                        expired += 1
            
            # 移除过期的不晋升条目
            for key in to_remove:
                del self.short_term[key]
            
            # 处理晋升条目
            for key, entry in to_promote:
                # 如果是operation类型，尝试合并
                if entry.tag == "operation":
                    merged = self._merge_operation_entries([entry], "mid_term")
                    if merged:
                        for merged_entry in merged:
                            self.mid_term[merged_entry.key] = merged_entry
                            promoted += 1
                else:
                    # 直接晋升
                    promoted_entry = deepcopy(entry)
                    promoted_entry.expires_at = self._calculate_expires_at("mid_term")
                    promoted_entry.promoted_from = "short_term"
                    self.mid_term[key] = promoted_entry
                    promoted += 1
                
                # 从短期移除
                del self.short_term[key]
            
            if promoted > 0 or expired > 0:
                self._meta["stats"]["promotions"]["short_to_mid"] += promoted
                self._meta["stats"]["cleanups"]["expired"] += expired
                self._mark_dirty()
                
            self.logger.debug(f"短期扫描完成: 晋升{promoted}, 过期{expired}")
            
            return {"promoted": promoted, "expired": expired}
            
        except Exception as e:
            self.logger.error(f"短期扫描失败: {e}")
            return {"promoted": 0, "expired": 0, "error": str(e)}

    def _run_mid_term_sweep(self) -> dict:
        """中期记忆扫描和晋升"""
        try:
            current_time = time.time()
            promoted = 0
            expired = 0
            to_remove = []
            to_promote = []
            
            for key, entry in self.mid_term.items():
                # 检查是否过期或容量满时强制检查
                force_check = len(self.mid_term) > self.config["mid_term_max_entries"]
                
                if (entry.expires_at and current_time > entry.expires_at) or force_check:
                    if self._should_promote_to_long(entry):
                        to_promote.append((key, entry))
                    else:
                        if not force_check:  # 只有真正过期才删除
                            to_remove.append(key)
                            expired += 1
            
            # 移除过期的不晋升条目
            for key in to_remove:
                del self.mid_term[key]
            
            # 处理晋升条目
            for key, entry in to_promote:
                promoted_entry = deepcopy(entry)
                promoted_entry.expires_at = None  # 长期记忆无过期时间
                promoted_entry.promoted_from = "mid_term"
                self.long_term[key] = promoted_entry
                promoted += 1
                
                # 从中期移除
                del self.mid_term[key]
            
            if promoted > 0 or expired > 0:
                self._meta["stats"]["promotions"]["mid_to_long"] += promoted
                self._meta["stats"]["cleanups"]["expired"] += expired
                self._mark_dirty()
            
            self.logger.debug(f"中期扫描完成: 晋升{promoted}, 过期{expired}")
            
            return {"promoted": promoted, "expired": expired}
            
        except Exception as e:
            self.logger.error(f"中期扫描失败: {e}")
            return {"promoted": 0, "expired": 0, "error": str(e)}

    def _run_capacity_check(self) -> dict:
        """容量检查和清理"""
        try:
            cleaned = 0
            
            # 检查各层容量
            layers = [
                ("short_term", self.short_term, self.config["short_term_max_entries"]),
                ("mid_term", self.mid_term, self.config["mid_term_max_entries"]),
                ("long_term", self.long_term, self.config["long_term_max_entries"])
            ]
            
            for layer_name, layer_storage, max_entries in layers:
                if len(layer_storage) > max_entries:
                    excess = len(layer_storage) - max_entries
                    cleaned += self._cleanup_layer(layer_storage, excess, layer_name)
            
            if cleaned > 0:
                self._meta["stats"]["cleanups"]["capacity"] += cleaned
                self._mark_dirty()
                self.logger.debug(f"容量清理完成: 清除{cleaned}条记录")
            
            return {"cleaned": cleaned}
            
        except Exception as e:
            self.logger.error(f"容量检查失败: {e}")
            return {"cleaned": 0, "error": str(e)}

    def _cleanup_layer(self, layer_storage: Dict[str, MemoryEntry], count: int, layer_name: str) -> int:
        """清理指定层级的记录"""
        if count <= 0:
            return 0
        
        # 获取所有条目并排序（低重要性 + 低访问频次 + 老旧的先删除）
        entries = list(layer_storage.items())
        current_time = time.time()
        
        def cleanup_score(item):
            key, entry = item
            # 计算清理优先级分数（越低越优先清理）
            importance_score = entry.importance
            access_score = min(entry.access_count / 10, 1.0)  # 归一化访问次数
            age_score = min((current_time - entry.created_at) / (30 * 24 * 3600), 1.0)  # 归一化年龄（30天）
            
            # context标签优先清理
            tag_penalty = -0.3 if entry.tag == "context" else 0
            
            return importance_score * 0.4 + access_score * 0.3 + (1 - age_score) * 0.2 + tag_penalty
        
        entries.sort(key=cleanup_score)
        
        # 删除最低分的记录
        cleaned = 0
        for i in range(min(count, len(entries))):
            key = entries[i][0]
            del layer_storage[key]
            cleaned += 1
            
        return cleaned

    def _run_dedup(self) -> dict:
        """去重处理"""
        try:
            merged = 0
            
            # 对每个层级进行去重
            for layer_name in ["short_term", "mid_term", "long_term"]:
                layer_storage = self._get_layer_by_name(layer_name)
                layer_merged = self._dedup_layer(layer_storage)
                merged += layer_merged
            
            if merged > 0:
                self._meta["stats"]["cleanups"]["dedup"] += merged
                self._mark_dirty()
                self.logger.debug(f"去重完成: 合并{merged}条记录")
            
            return {"merged": merged}
            
        except Exception as e:
            self.logger.error(f"去重处理失败: {e}")
            return {"merged": 0, "error": str(e)}

    def _dedup_layer(self, layer_storage: Dict[str, MemoryEntry]) -> int:
        """对单个层级进行去重"""
        merged = 0
        to_remove = []
        
        entries = list(layer_storage.items())
        
        # 按标签分组进行去重
        tag_groups = {}
        for key, entry in entries:
            if entry.tag not in tag_groups:
                tag_groups[entry.tag] = []
            tag_groups[entry.tag].append((key, entry))
        
        for tag, group_entries in tag_groups.items():
            if len(group_entries) < 2:
                continue
                
            # 查找相似的条目
            for i in range(len(group_entries)):
                if group_entries[i][0] in to_remove:
                    continue
                    
                key1, entry1 = group_entries[i]
                
                for j in range(i + 1, len(group_entries)):
                    if group_entries[j][0] in to_remove:
                        continue
                        
                    key2, entry2 = group_entries[j]
                    
                    # 检查是否应该合并
                    if self._should_merge_entries(entry1, entry2):
                        # 合并到访问次数更多的条目
                        if entry1.access_count >= entry2.access_count:
                            self._merge_entry_into(entry1, entry2)
                            to_remove.append(key2)
                        else:
                            self._merge_entry_into(entry2, entry1)
                            to_remove.append(key1)
                        merged += 1
                        break
        
        # 移除被合并的条目
        for key in to_remove:
            if key in layer_storage:
                del layer_storage[key]
        
        return merged

    def _should_promote_to_mid(self, entry: MemoryEntry) -> bool:
        """判断是否应该从短期晋升到中期"""
        # context类型直接丢弃
        if entry.tag == "context":
            return False
        
        # 高访问频次直接晋升
        if entry.access_count >= 3:
            return True
        
        # operation和crash类型总是尝试晋升（会在晋升时合并）
        if entry.tag in ["operation", "crash"]:
            return True
        
        # 其他类型根据重要性决定
        return entry.importance >= 0.6

    def _should_promote_to_long(self, entry: MemoryEntry) -> bool:
        """判断是否应该从中期晋升到长期"""
        # 高访问频次
        if entry.access_count >= 5:
            return True
        
        # crash类型且重要性高
        if entry.tag == "crash" and entry.importance >= 0.7:
            return True
        
        # convention和fact类型且有一定访问频次
        if entry.tag in ["convention", "fact"] and entry.access_count >= 3:
            return True
        
        # 极高重要性
        if entry.importance >= 0.8:
            return True
        
        return False

    def _should_merge_entries(self, entry1: MemoryEntry, entry2: MemoryEntry) -> bool:
        """判断两个条目是否应该合并"""
        # 必须是相同标签
        if entry1.tag != entry2.tag:
            return False
        
        # 精确key匹配
        if entry1.key == entry2.key:
            return True
        
        # crash类型的前缀匹配
        if entry1.tag == "crash":
            prefix1 = ":".join(entry1.key.split(":")[:3])  # crash:tool:action
            prefix2 = ":".join(entry2.key.split(":")[:3])
            if prefix1 == prefix2:
                return True
        
        # 文本相似度检查
        similarity = SequenceMatcher(None, str(entry1.value), str(entry2.value)).ratio()
        if similarity > self.config["dedup_similarity_threshold"]:
            return True
        
        return False

    def _merge_entry_into(self, target: MemoryEntry, source: MemoryEntry):
        """将source条目合并到target条目"""
        # 累加访问次数
        target.access_count += source.access_count
        
        # 取更高的重要性
        target.importance = max(target.importance, source.importance)
        
        # 更新最后访问时间
        target.last_accessed = max(target.last_accessed, source.last_accessed)
        
        # 如果是相同内容，保持原样；如果不同，可以考虑合并信息
        if target.key == source.key and target.value != source.value:
            # 对于operation类型，可以合并统计信息
            if target.tag == "operation" and isinstance(target.value, dict) and isinstance(source.value, dict):
                if "count" in target.value:
                    target.value["count"] += source.value.get("count", 1)
                else:
                    target.value["count"] = 2

    def _merge_operation_entries(self, entries: List[MemoryEntry], target_layer: str) -> List[MemoryEntry]:
        """合并操作记录"""
        if not entries:
            return []
        
        # 按工具和动作分组
        groups = {}
        for entry in entries:
            if entry.tag != "operation":
                continue
                
            operation_data = entry.value
            if not isinstance(operation_data, dict):
                continue
                
            tool = operation_data.get("tool", "unknown")
            action = operation_data.get("action", "unknown")
            group_key = f"{tool}:{action}"
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(entry)
        
        # 创建合并后的条目
        merged_entries = []
        for group_key, group_entries in groups.items():
            if len(group_entries) == 1:
                # 单个条目直接使用
                merged_entry = deepcopy(group_entries[0])
                merged_entry.expires_at = self._calculate_expires_at(target_layer)
                merged_entry.promoted_from = "short_term"
                merged_entries.append(merged_entry)
            else:
                # 多个条目合并为摘要
                merged_entry = self._create_operation_summary(group_entries, target_layer)
                if merged_entry:
                    merged_entries.append(merged_entry)
        
        return merged_entries

    def _create_operation_summary(self, entries: List[MemoryEntry], target_layer: str) -> Optional[MemoryEntry]:
        """创建操作摘要条目"""
        if not entries:
            return None
        
        first_entry = entries[0]
        operation_data = first_entry.value
        
        if not isinstance(operation_data, dict):
            return None
        
        tool = operation_data.get("tool", "unknown")
        action = operation_data.get("action", "unknown")
        
        # 统计信息
        total_count = len(entries)
        success_count = sum(1 for e in entries if e.value.get("success", False))
        total_duration = sum(e.value.get("duration_ms", 0) for e in entries)
        
        # 创建摘要
        summary_data = {
            "type": "operation_summary",
            "tool": tool,
            "action": action,
            "total_executions": total_count,
            "success_count": success_count,
            "success_rate": success_count / total_count,
            "avg_duration_ms": total_duration // total_count if total_count > 0 else 0,
            "created_from": "short_term_batch",
            "last_execution": max(e.value.get("timestamp", 0) for e in entries)
        }
        
        summary_key = f"operation_summary:{tool}:{action}"
        
        summary_entry = MemoryEntry(
            key=summary_key,
            value=summary_data,
            tag="operation",
            importance=min(0.8, 0.4 + (success_count / total_count) * 0.4),  # 基于成功率调整重要性
            source=f"{tool}.batch",
            expires_at=self._calculate_expires_at(target_layer),
            promoted_from="short_term"
        )
        
        # 累加访问次数
        summary_entry.access_count = sum(e.access_count for e in entries)
        summary_entry.last_accessed = max(e.last_accessed for e in entries)
        
        return summary_entry

    # === 导出和统计 ===
    
    def export_briefing(self, max_tokens: int = 1500, include_team: bool = True,
                        first_message: bool = True) -> str:
        """导出记忆简报
        
        Args:
            max_tokens: 最大token数量（硬上限，超出截断）
            include_team: 是否包含团队记忆
            first_message: 是否为首条消息（首条消息包含 conventions/platform_diff）
            
        Token 预算分配:
            - 团队 crash_rules + gotchas: ~500 token (按 DCC 过滤后)
            - 团队 conventions + platform_diff: ~300 token (仅首条消息)
            - 个人记忆: 剩余 budget
            
        Returns:
            格式化的记忆简报文本
        """
        try:
            sections = []
            current_tokens = 0
            
            def estimate_tokens(text: str) -> int:
                return len(text) // 4
            
            def add_section(title: str, items: List[str], emoji: str = ""):
                nonlocal current_tokens, sections
                if not items:
                    return
                
                section_text = f"{emoji} {title}:\n"
                for item in items:
                    item_line = f"- {item}\n"
                    if current_tokens + estimate_tokens(section_text + item_line) > max_tokens:
                        break
                    section_text += item_line
                
                if section_text.strip().endswith(":"):
                    return  # 没有添加任何条目
                
                sections.append(section_text)
                current_tokens += estimate_tokens(section_text)
            
            # === 团队记忆 (P0, 优先级最高) ===
            if include_team and self._team_memory_cache:
                # 按命中次数排序的辅助函数（高频在前，同频保持原序）
                def _sort_by_hits(rules: List[str]) -> List[str]:
                    return sorted(rules, key=lambda r: self._get_team_hit_count(r), reverse=True)
                
                # P0: 团队 crash rules (每次必读)
                team_crashes = _sort_by_hits(self._team_memory_cache.get("crash_rules.md", []))
                add_section("TEAM CRASH RULES", team_crashes[:15], "\u26a0\ufe0f")
                
                # P0: 团队 gotchas (每次必读)
                team_gotchas = _sort_by_hits(self._team_memory_cache.get("gotchas.md", []))
                add_section("TEAM GOTCHAS", team_gotchas[:20], "\u26a0\ufe0f")
                
                # P1: 仅首条消息
                if first_message:
                    team_conventions = _sort_by_hits(self._team_memory_cache.get("conventions.md", []))
                    add_section("TEAM CONVENTIONS", team_conventions[:10], "\U0001f4d0")
                    
                    team_platform = _sort_by_hits(self._team_memory_cache.get("platform_differences.md", []))
                    add_section("PLATFORM DIFFERENCES", team_platform[:10], "\U0001f310")
            
            # === 个人记忆 ===
            
            # P2: 个人崩溃规则
            crash_entries = []
            for layer_name in ["long_term", "mid_term", "short_term"]:
                layer_storage = self._get_layer_by_name(layer_name)
                for key, entry in layer_storage.items():
                    if entry.tag == "crash" and isinstance(entry.value, dict):
                        rule = entry.value.get("avoidance_rule", "").strip()
                        if rule:
                            crash_entries.append(f"{entry.value.get('tool', 'unknown')}: {rule}")
            
            add_section("PERSONAL CRASH RULES", crash_entries[:10], "\u26a0\ufe0f")
            
            # P3: 个人 pattern (反直觉行为/经验教训)
            pattern_entries = []
            for layer_name in ["long_term", "mid_term", "short_term"]:
                layer_storage = self._get_layer_by_name(layer_name)
                for key, entry in sorted(layer_storage.items(),
                                       key=lambda x: x[1].importance, reverse=True):
                    if entry.tag == "pattern":
                        if isinstance(entry.value, dict):
                            # RetryTracker 自动提取的 pattern
                            val = entry.value.get("fix", str(entry.value))[:80]
                        else:
                            val = str(entry.value)[:80]
                        pattern_entries.append(f"{entry.key}: {val}")
                        if len(pattern_entries) >= 8:
                            break
            
            add_section("LEARNED PATTERNS", pattern_entries[:6], "\U0001f4a1")
            
            # P4: 约定规则
            convention_entries = []
            for layer_name in ["long_term", "mid_term", "short_term"]:
                layer_storage = self._get_layer_by_name(layer_name)
                for key, entry in layer_storage.items():
                    if entry.tag == "convention":
                        value_str = str(entry.value)[:100]
                        convention_entries.append(f"{entry.key}: {value_str}")
            
            add_section("CONVENTIONS", convention_entries[:10], "\U0001f4d0")
            
            # P5: 偏好 (前N条)
            preference_entries = []
            for layer_name in ["long_term", "mid_term", "short_term"]:
                layer_storage = self._get_layer_by_name(layer_name)
                for key, entry in sorted(layer_storage.items(), key=lambda x: x[1].importance, reverse=True):
                    if entry.tag == "preference":
                        value_str = str(entry.value)[:80]
                        preference_entries.append(f"{entry.key}: {value_str}")
                        if len(preference_entries) >= 8:
                            break
            
            add_section("PREFERENCES", preference_entries[:6], "\U0001f3a8")
            
            # 组装最终简报
            if sections:
                briefing = "[Memory Briefing]\n" + "\n".join(sections)
            else:
                briefing = "[Memory Briefing]\n记忆库为空或无重要信息"
            
            return briefing
            
        except Exception as e:
            self.logger.error(f"导出简报失败: {e}")
            return f"[Memory Briefing]\n导出简报时出错: {str(e)}"

    def get_stats(self) -> dict:
        """获取统计信息"""
        try:
            with self._lock:
                current_time = time.time()
                
                # 计算各层级统计
                layer_stats = {}
                for layer_name in MEMORY_LAYERS:
                    layer_storage = self._get_layer_by_name(layer_name)
                    
                    # 按标签统计
                    tag_counts = {}
                    total_importance = 0
                    total_access = 0
                    expired_count = 0
                    
                    for entry in layer_storage.values():
                        # 标签统计
                        tag_counts[entry.tag] = tag_counts.get(entry.tag, 0) + 1
                        
                        # 重要性和访问统计
                        total_importance += entry.importance
                        total_access += entry.access_count
                        
                        # 过期统计
                        if entry.expires_at and current_time > entry.expires_at:
                            expired_count += 1
                    
                    layer_stats[layer_name] = {
                        "total_entries": len(layer_storage),
                        "tag_distribution": tag_counts,
                        "avg_importance": total_importance / len(layer_storage) if layer_storage else 0,
                        "total_accesses": total_access,
                        "expired_entries": expired_count
                    }
                
                # 整体统计
                total_entries = sum(stats["total_entries"] for stats in layer_stats.values())
                
                stats = {
                    "version": self._meta["version"],
                    "dcc": self._meta["dcc"],
                    "created": self._meta["created"],
                    "last_maintenance": self._meta["last_maintenance"],
                    "last_save": self._meta["last_save"],
                    "total_entries": total_entries,
                    "layer_stats": layer_stats,
                    "system_stats": self._meta["stats"].copy(),
                    "config": self.config.copy(),
                    "storage_path": self.storage_path,
                    "memory_health": self._calculate_memory_health()
                }
                
                return stats
                
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}

    def _calculate_memory_health(self) -> dict:
        """计算记忆健康度"""
        try:
            health = {
                "overall_score": 0.0,
                "capacity_usage": {},
                "age_distribution": {},
                "access_patterns": {},
                "issues": []
            }
            
            # 容量使用率
            for layer_name in MEMORY_LAYERS:
                layer_storage = self._get_layer_by_name(layer_name)
                max_key = f"{layer_name}_max_entries"
                max_entries = self.config[max_key]
                usage_ratio = len(layer_storage) / max_entries
                
                health["capacity_usage"][layer_name] = {
                    "current": len(layer_storage),
                    "max": max_entries,
                    "usage_ratio": usage_ratio
                }
                
                if usage_ratio > 0.9:
                    health["issues"].append(f"{layer_name}容量使用率过高: {usage_ratio:.1%}")
                elif usage_ratio > 0.8:
                    health["issues"].append(f"{layer_name}容量使用率较高: {usage_ratio:.1%}")
            
            # 年龄分布检查
            current_time = time.time()
            age_buckets = {"fresh": 0, "recent": 0, "old": 0, "stale": 0}
            
            for layer_name in MEMORY_LAYERS:
                layer_storage = self._get_layer_by_name(layer_name)
                for entry in layer_storage.values():
                    age_hours = (current_time - entry.created_at) / 3600
                    
                    if age_hours < 24:
                        age_buckets["fresh"] += 1
                    elif age_hours < 168:  # 1周
                        age_buckets["recent"] += 1
                    elif age_hours < 720:  # 1个月
                        age_buckets["old"] += 1
                    else:
                        age_buckets["stale"] += 1
            
            health["age_distribution"] = age_buckets
            
            # 访问模式检查
            zero_access = 0
            high_access = 0
            total_entries = sum(len(self._get_layer_by_name(layer)) for layer in MEMORY_LAYERS)
            
            for layer_name in MEMORY_LAYERS:
                layer_storage = self._get_layer_by_name(layer_name)
                for entry in layer_storage.values():
                    if entry.access_count == 0:
                        zero_access += 1
                    elif entry.access_count >= 5:
                        high_access += 1
            
            health["access_patterns"] = {
                "zero_access": zero_access,
                "high_access": high_access,
                "zero_access_ratio": zero_access / total_entries if total_entries > 0 else 0
            }
            
            if zero_access / total_entries > 0.3 if total_entries > 0 else False:
                health["issues"].append(f"未访问记录过多: {zero_access}/{total_entries}")
            
            # 计算整体评分
            capacity_score = 1.0 - max(health["capacity_usage"][layer]["usage_ratio"] for layer in MEMORY_LAYERS)
            access_score = 1.0 - health["access_patterns"]["zero_access_ratio"]
            issue_score = max(0, 1.0 - len(health["issues"]) * 0.1)
            
            health["overall_score"] = (capacity_score * 0.4 + access_score * 0.3 + issue_score * 0.3)
            
            return health
            
        except Exception as e:
            return {"error": str(e), "overall_score": 0.0}

    # === 迁移功能 ===
    
    @staticmethod
    def migrate_from_ue_v1(base_dir: str, target_path: str) -> int:
        """从UE v1格式迁移
        
        Args:
            base_dir: UE v1记忆文件目录
            target_path: 目标v2文件路径
            
        Returns:
            迁移的记录数量
        """
        try:
            migrated_count = 0
            
            # 创建新的管理器实例
            manager = MemoryManagerV2(target_path, "migrated_from_ue_v1")
            
            # 迁移文件映射
            v1_files = {
                "memory_facts.json": "fact",
                "memory_preferences.json": "preference", 
                "memory_conventions.json": "convention"
            }
            
            for filename, tag in v1_files.items():
                file_path = os.path.join(base_dir, filename)
                if not os.path.exists(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 处理不同的数据格式
                    if isinstance(data, dict):
                        for key, value in data.items():
                            manager.record(key, value, tag, 0.7, f"ue_v1_{filename}")
                            migrated_count += 1
                    elif isinstance(data, list):
                        for i, item in enumerate(data):
                            key = f"{tag}_{i}"
                            manager.record(key, item, tag, 0.7, f"ue_v1_{filename}")
                            migrated_count += 1
                    
                    # 备份原文件
                    backup_path = file_path + ".bak"
                    shutil.copy2(file_path, backup_path)
                    
                    print(f"已迁移 {filename}: {migrated_count} 条记录")
                    
                except Exception as e:
                    print(f"迁移 {filename} 失败: {e}")
            
            # 保存迁移结果
            manager._save()
            
            print(f"UE v1迁移完成，总计: {migrated_count} 条记录")
            return migrated_count
            
        except Exception as e:
            print(f"UE v1迁移失败: {e}")
            return 0

    @staticmethod  
    def migrate_from_dcc_v1(old_file: str, target_path: str) -> int:
        """从DCC v1格式迁移
        
        Args:
            old_file: 旧版memory.json文件路径
            target_path: 目标v2文件路径
            
        Returns:
            迁移的记录数量
        """
        try:
            if not os.path.exists(old_file):
                print(f"源文件不存在: {old_file}")
                return 0
            
            migrated_count = 0
            
            with open(old_file, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            # 创建新的管理器实例
            manager = MemoryManagerV2(target_path, "migrated_from_dcc_v1")
            
            # 处理旧格式数据
            if isinstance(old_data, dict):
                for key, value in old_data.items():
                    # 尝试从key推断标签
                    tag = "fact"  # 默认
                    if "pref" in key.lower() or "setting" in key.lower():
                        tag = "preference"
                    elif "rule" in key.lower() or "convention" in key.lower():
                        tag = "convention"
                    elif "crash" in key.lower() or "error" in key.lower():
                        tag = "crash"
                    elif "op" in key.lower() or "operation" in key.lower():
                        tag = "operation"
                    
                    manager.record(key, value, tag, 0.6, "dcc_v1_migration")
                    migrated_count += 1
            
            # 备份原文件
            backup_path = old_file + ".bak"
            shutil.copy2(old_file, backup_path)
            
            # 保存迁移结果
            manager._save()
            
            print(f"DCC v1迁移完成: {migrated_count} 条记录")
            return migrated_count
            
        except Exception as e:
            print(f"DCC v1迁移失败: {e}")
            return 0


# === 使用示例和测试功能 ===

def test_memory_manager():
    """测试记忆管理器基础功能"""
    import tempfile
    
    # 创建临时存储文件
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        storage_path = f.name
    
    try:
        # 创建管理器实例
        manager = MemoryManagerV2(storage_path, "test_dcc")
        
        print("=== 测试基础CRUD操作 ===")
        
        # 测试记录
        assert manager.record("test_fact", "这是一个测试事实", "fact", 0.8)
        assert manager.record("test_pref", {"color": "blue", "size": "large"}, "preference", 0.6)
        assert manager.record("test_conv", "使用驼峰命名", "convention", 0.9)
        
        # 测试获取
        fact = manager.get("test_fact")
        assert fact is not None
        assert fact["value"] == "这是一个测试事实"
        print(f"获取事实: {fact['key']}")
        
        # 测试搜索
        results = manager.search("测试")
        assert len(results) > 0
        print(f"搜索结果: {len(results)} 条")
        
        # 测试列出条目
        entries = manager.list_entries(tag="fact")
        print(f"事实条目: {len(entries)} 条")
        
        print("=== 测试操作记录 ===")
        
        # 记录操作
        manager.record_operation("test_tool", "create_cube", "size=1", "success", 1500)
        manager.record_operation("test_tool", "create_cube", "size=2", "success", 1200)
        manager.record_operation("test_tool", "delete_all", "", "failed", 500, "Permission denied")
        
        # 记录崩溃
        manager.record_crash("test_tool", "import_fbx", "file=big_model.fbx", 
                           "Memory allocation failed", "文件过大导致内存不足", 
                           "导入前检查文件大小，超过100MB先压缩", "high")
        
        # 检查操作历史
        op_check = manager.check_operation("test_tool", "create")
        print(f"操作检查结果: 成功率 {op_check['success_rate']:.1%}")
        
        print("=== 测试维护功能 ===")
        
        # 执行维护
        maintain_stats = manager.maintain(full=True)
        print(f"维护统计: {maintain_stats}")
        
        print("=== 测试导出功能 ===")
        
        # 导出简报
        briefing = manager.export_briefing(max_tokens=800, include_team=True)
        print(f"记忆简报:\n{briefing}")
        
        # 获取统计信息
        stats = manager.get_stats()
        print(f"统计信息: 总记录 {stats['total_entries']} 条，健康度 {stats['memory_health']['overall_score']:.2f}")
        
        print("=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        return False
    
    finally:
        # 清理临时文件
        try:
            os.unlink(storage_path)
        except:
            pass


if __name__ == "__main__":
    # 设置控制台编码
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    
    # 运行测试
    if test_memory_manager():
        print("✓ 记忆管理器测试通过")
    else:
        print("✗ 记忆管理器测试失败")