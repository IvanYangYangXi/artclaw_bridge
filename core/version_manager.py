"""
ArtClaw Version Manager SDK
============================

统一的 Skill/Tool 版本管理模块，供所有端（CLI / DCC / UE / ToolManager）复用。

取代以下分散实现：
  - cli/artclaw_bridge/skill_hub.py 中的版本函数
  - UEClawBridge/Content/Python/skill_version.py
  - DCCClawBridge/core/skill_sync.py 中的 _version_gt

使用示例：
    from version_manager import VersionManager, parse_version, matches_skill

    # 独立函数使用
    v = parse_version("5.4.1-preview")  # → (5, 4, 1)
    ok = matches_skill(manifest, "unreal_engine", "5.4.1")

    # VersionManager 类使用
    # 安装目录为扁平结构：~/.openclaw/workspace/skills/{skill_name}/
    # source_paths 是源码端的分层目录，层级只在源码端存在
    mgr = VersionManager(
        installed_path="~/.openclaw/workspace/skills",
        source_paths={
            "00_official": "/path/to/project/skills/official",
            "02_user":     "~/.artclaw/skills",
        },
    )
    status = mgr.check_skill_sync("my_skill")
    result = mgr.install(source_dir)           # 安装到扁平目录，无层级子目录
    result = mgr.install(source_dir, source_layer="00_official")  # source_layer 仅作来源标记
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ── 层级优先级常量 ────────────────────────────────────────────────────────────

LAYER_PRIORITY: Dict[str, int] = {
    "00_official": 0,
    "01_team": 1,
    "02_user": 2,
    "99_custom": 99,
}
"""层级名 → 优先级数值，数值越小优先级越高。"""


# ── 数据类 ────────────────────────────────────────────────────────────────────

class SyncState(str, Enum):
    SYNCED = "synced"
    SOURCE_NEWER = "source_newer"
    INSTALLED_NEWER = "installed_newer"
    MODIFIED = "modified"
    CONFLICT = "conflict"
    NO_SOURCE = "no_source"
    NOT_INSTALLED = "not_installed"


@dataclass
class SyncStatus:
    state: SyncState
    changed_files: List[str] = field(default_factory=list)
    source_version: Optional[str] = None
    installed_version: Optional[str] = None
    skill_name: str = ""


@dataclass
class ConflictInfo:
    skill_name: str
    layers: List[str]        # 所有包含此 Skill 的层级，按优先级排序
    active_layer: str        # 实际生效的层级（最高优先级）
    shadowed_layers: List[str]  # 被覆盖的层级


@dataclass
class InstallResult:
    success: bool
    skill_name: str = ""
    version: str = ""
    installed_to: str = ""
    deps_installed: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class PublishResult:
    success: bool
    skill_name: str = ""
    from_layer: str = ""
    to_layer: str = ""
    version: str = ""
    error: Optional[str] = None


# ── 版本解析与比较函数 ────────────────────────────────────────────────────────

def parse_version(version_str: str) -> Tuple[int, ...]:
    """
    解析语义版本字符串为整数元组。

    支持格式：
      "1.2.3"          → (1, 2, 3)
      "v5.4.1"         → (5, 4, 1)
      "5.4.1-preview"  → (5, 4, 1)  # 预发布后缀被忽略
      "5.4.1+build.1"  → (5, 4, 1)  # build metadata 被忽略
      "5.4"            → (5, 4)
      ""               → (0, 0, 0)
    """
    if not version_str:
        return (0, 0, 0)
    # 去掉 v 前缀，去掉 -prerelease 和 +build 后缀
    clean = version_str.strip().lstrip("v").split("-")[0].split("+")[0]
    try:
        parts = clean.split(".")
        return tuple(int(re.match(r"\d+", p).group()) for p in parts if re.match(r"\d+", p))
    except Exception:
        return (0, 0, 0)


def compare_versions(v1: str, v2: str) -> int:
    """
    比较两个版本字符串。
    返回 1 (v1 > v2), -1 (v1 < v2), 0 (相等)
    """
    t1, t2 = parse_version(v1), parse_version(v2)
    # 对齐长度
    max_len = max(len(t1), len(t2))
    t1 = t1 + (0,) * (max_len - len(t1))
    t2 = t2 + (0,) * (max_len - len(t2))
    if t1 > t2:
        return 1
    if t1 < t2:
        return -1
    return 0


def version_gte(v1: str, v2: str) -> bool:
    """v1 >= v2"""
    return compare_versions(v1, v2) >= 0


def version_lte(v1: str, v2: str) -> bool:
    """v1 <= v2"""
    return compare_versions(v1, v2) <= 0


def version_eq(v1: str, v2: str) -> bool:
    """v1 == v2"""
    return compare_versions(v1, v2) == 0


def version_gt(v1: str, v2: str) -> bool:
    """v1 > v2"""
    return compare_versions(v1, v2) > 0


def version_lt(v1: str, v2: str) -> bool:
    """v1 < v2"""
    return compare_versions(v1, v2) < 0


# ── Skill 匹配函数 ────────────────────────────────────────────────────────────

def matches_software_version(
    constraint: Dict[str, str],
    current_version: str,
) -> bool:
    """
    检查当前软件版本是否满足 manifest.software_version 约束。

    :param constraint: {"min": "5.3", "max": "5.5"} 或 {}
    :param current_version: 如 "5.4.1"
    """
    if not constraint:
        return True
    min_v = constraint.get("min", "")
    max_v = constraint.get("max", "")
    if min_v and not version_gte(current_version, min_v):
        return False
    if max_v and not version_lte(current_version, max_v):
        return False
    return True


def matches_skill(
    manifest: Dict[str, Any],
    current_software: str,
    current_version: str,
) -> bool:
    """
    检查 Skill manifest 是否与当前 DCC 软件 + 版本匹配。

    匹配规则：
    1. manifest.software == "universal"，OR manifest.software == current_software
    2. 如果 manifest 有 software_version，当前版本需在范围内
    """
    skill_software = manifest.get("software", "universal")
    if skill_software != "universal" and skill_software != current_software:
        return False
    sw_ver = manifest.get("software_version", {})
    if sw_ver and not matches_software_version(sw_ver, current_version):
        return False
    return True


def version_distance(
    constraint: Dict[str, str],
    current_version: str,
) -> float:
    """
    计算版本"距离"，用于从多个候选 Skill 中选最精确匹配。

    距离越小 = 版本范围越精确：
    - 无约束（{}）      → 1000.0（最低优先级）
    - 有范围约束        → 范围大小（min 到 max 的整数步数之和）
    - min == max（精确）→ 0.0（最高优先级）
    """
    if not constraint:
        return 1000.0
    min_v = constraint.get("min", "")
    max_v = constraint.get("max", "")
    if not min_v and not max_v:
        return 1000.0
    if min_v and max_v:
        t_min = parse_version(min_v)
        t_max = parse_version(max_v)
        # 计算各分量的差值之和作为距离
        max_len = max(len(t_min), len(t_max))
        t_min = t_min + (0,) * (max_len - len(t_min))
        t_max = t_max + (0,) * (max_len - len(t_max))
        return float(sum(abs(a - b) for a, b in zip(t_min, t_max)))
    # 只有 min 或只有 max：计算当前版本到约束的距离
    t_cur = parse_version(current_version)
    t_ref = parse_version(min_v or max_v)
    max_len = max(len(t_cur), len(t_ref))
    t_cur = t_cur + (0,) * (max_len - len(t_cur))
    t_ref = t_ref + (0,) * (max_len - len(t_ref))
    return float(sum(abs(a - b) for a, b in zip(t_cur, t_ref)))


def select_best_match(
    candidates: List[Any],
    current_software: str,
    current_version: str,
    manifest_key: Optional[Callable] = None,
) -> Optional[Tuple[int, Any]]:
    """
    从多个候选中选择最佳匹配（最小 version_distance）。

    :param candidates: 候选列表（manifest 字典，或包含 manifest 的对象）
    :param current_software: 当前 DCC 软件类型，如 "unreal_engine"
    :param current_version: 当前 DCC 版本，如 "5.4.1"
    :param manifest_key: 从候选元素提取 manifest 字典的函数，默认 lambda x: x
    :return: (index, best_candidate)，找不到返回 None
    """
    key = manifest_key or (lambda x: x)
    best_idx, best_item, best_dist = None, None, float("inf")
    for i, item in enumerate(candidates):
        m = key(item)
        if not matches_skill(m, current_software, current_version):
            continue
        dist = version_distance(m.get("software_version", {}), current_version)
        if dist < best_dist:
            best_dist, best_idx, best_item = dist, i, item
    if best_idx is None:
        return None
    return best_idx, best_item


# ── 哈希同步检测函数 ──────────────────────────────────────────────────────────

def _file_hash(path: Path) -> str:
    """计算单个文件的 MD5 哈希值。"""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _dir_hashes(root: Path) -> Dict[str, str]:
    """计算目录中所有 .py/.md/.json 文件的 MD5 哈希，返回 {相对路径: hash}"""
    result: Dict[str, str] = {}
    if not root.exists():
        return result
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.suffix not in {".py", ".md", ".json"}:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        result[rel] = _file_hash(p)
    return result


def _extract_version_from_dir(skill_dir: Path) -> Optional[str]:
    """从 Skill 目录提取版本号（manifest.json 优先，SKILL.md 次之）"""
    manifest_path = skill_dir / "manifest.json"
    if manifest_path.exists():
        try:
            v = json.loads(manifest_path.read_text(encoding="utf-8")).get("version", "")
            if v:
                return str(v)
        except Exception:
            pass
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding="utf-8")
            m = re.search(r'^version\s*:\s*(.+)$', content, re.MULTILINE)
            if m:
                return m.group(1).strip().strip("\"'")
        except Exception:
            pass
    return None


def compare_skill_dirs(
    installed_dir: Path,
    source_dir: Path,
) -> SyncStatus:
    """
    比较已安装目录和源码目录，返回同步状态。

    策略（哈希优先）：
    1. 计算所有 .py/.md/.json 文件的 MD5 哈希
    2. hash 完全相同 → SYNCED
    3. hash 不同：用文件 mtime 判断哪侧更新
    4. 用 manifest.version 辅助确认方向

    状态含义：
      SYNCED          — 完全一致
      SOURCE_NEWER    — 源码比安装版本新（建议更新安装）
      INSTALLED_NEWER — 安装版本比源码新（建议发布）
      MODIFIED        — 有差异但版本号相同（本地有未发布改动）
      CONFLICT        — 两侧都有修改（需手动处理）
      NO_SOURCE       — 找不到源码目录
    """
    skill_name = installed_dir.name
    inst_ver = _extract_version_from_dir(installed_dir)

    if not source_dir or not source_dir.exists():
        return SyncStatus(
            state=SyncState.NO_SOURCE,
            skill_name=skill_name,
            installed_version=inst_ver,
        )

    src_ver = _extract_version_from_dir(source_dir)
    hashes_inst = _dir_hashes(installed_dir)
    hashes_src = _dir_hashes(source_dir)

    if hashes_inst == hashes_src:
        return SyncStatus(
            state=SyncState.SYNCED,
            skill_name=skill_name,
            installed_version=inst_ver,
            source_version=src_ver,
        )

    # 找出变更文件并判断方向
    all_files = set(hashes_inst.keys()) | set(hashes_src.keys())
    changed: List[str] = []
    inst_ahead = False
    src_ahead = False

    for f in sorted(all_files):
        h_inst = hashes_inst.get(f, "")
        h_src = hashes_src.get(f, "")
        if h_inst == h_src:
            continue
        changed.append(f)
        if not h_inst:
            src_ahead = True   # 源码有但安装没有 → 源码新
        elif not h_src:
            inst_ahead = True  # 安装有但源码没有 → 安装新
        else:
            try:
                mt_inst = (installed_dir / f).stat().st_mtime
                mt_src = (source_dir / f).stat().st_mtime
                if mt_src > mt_inst:
                    src_ahead = True
                elif mt_inst > mt_src:
                    inst_ahead = True
                else:
                    inst_ahead = src_ahead = True
            except Exception:
                inst_ahead = src_ahead = True

    if inst_ahead and src_ahead:
        state = SyncState.CONFLICT
    elif src_ahead:
        state = SyncState.SOURCE_NEWER
    elif inst_ahead:
        # 用版本号辅助确认
        if inst_ver and src_ver and compare_versions(inst_ver, src_ver) > 0:
            state = SyncState.INSTALLED_NEWER
        else:
            state = SyncState.MODIFIED
    else:
        state = SyncState.MODIFIED

    return SyncStatus(
        state=state,
        changed_files=changed,
        skill_name=skill_name,
        installed_version=inst_ver,
        source_version=src_ver,
    )


# ── 冲突检测 ──────────────────────────────────────────────────────────────────

def detect_layer_conflicts(
    layer_skills: Dict[str, List[str]],
) -> List[ConflictInfo]:
    """
    检测分层 Skill 库中的命名冲突。

    :param layer_skills: {"00_official": ["skill_a", "skill_b"], "02_user": ["skill_a"]}
    :return: ConflictInfo 列表，每个冲突对应一个条目
    """
    # 收集每个 skill 出现在哪些层级
    skill_to_layers: Dict[str, List[str]] = {}
    for layer, skills in layer_skills.items():
        for s in skills:
            skill_to_layers.setdefault(s, []).append(layer)

    conflicts: List[ConflictInfo] = []
    for skill_name, layers in skill_to_layers.items():
        if len(layers) < 2:
            continue
        # 按优先级排序
        sorted_layers = sorted(layers, key=lambda l: LAYER_PRIORITY.get(l, 99))
        active = sorted_layers[0]
        shadowed = sorted_layers[1:]
        conflicts.append(ConflictInfo(
            skill_name=skill_name,
            layers=sorted_layers,
            active_layer=active,
            shadowed_layers=shadowed,
        ))
    return conflicts


# ── VersionManager 主类 ───────────────────────────────────────────────────────

class VersionManager:
    """
    ArtClaw Skill/Tool 版本管理 SDK 主类。

    封装安装、更新、发布、版本比较等所有版本管理操作的统一接口，
    供 CLI / DCC 插件 / UE 插件 / Tool Manager 所有端复用。

    示例：
        mgr = VersionManager(
            installed_path="~/.openclaw/workspace/skills",
            source_paths={
                "00_official": "/path/to/skills/official",
                "02_user":     "~/.artclaw/skills",
            },
        )
        sync = mgr.check_skill_sync("my_skill")
        result = mgr.install(Path("/path/to/my_skill"))
        mgr.disable("my_skill")
    """

    DEFAULT_CONFIG_PATH = Path.home() / ".artclaw" / "config.json"

    def __init__(
        self,
        installed_path: Optional[Any] = None,
        source_paths: Optional[Dict[str, Any]] = None,
        config_path: Optional[Any] = None,
        project_root: Optional[Any] = None,
    ):
        self.installed_path = Path(installed_path).expanduser() if installed_path else None
        self.source_paths: Dict[str, Path] = {}
        if source_paths:
            for layer, p in source_paths.items():
                self.source_paths[layer] = Path(p).expanduser()
        self.config_path = Path(config_path).expanduser() if config_path else self.DEFAULT_CONFIG_PATH
        # project_root：Tool/Workflow 官方/市集资源的根目录
        # 官方/市集资源不复制，直接从 {project_root}/tools/ 或 {project_root}/workflows/ 读取
        self._project_root = Path(project_root).expanduser() if project_root else None

    # ── 私有辅助 ──────────────────────────────────────────────────────────────

    def _read_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _write_config(self, cfg: Dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _read_manifest(self, skill_dir: Path) -> Optional[Dict[str, Any]]:
        manifest_path = skill_dir / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _find_skill_dir(self, skill_name: str) -> Optional[Path]:
        """
        在 installed_path 中查找指定名称的 Skill 目录。

        安装目录为扁平结构（OpenClaw 规范），即：
          ~/.openclaw/workspace/skills/{skill_name}/
        不存在层级子目录，层级（00_official / 02_user 等）只在源码端使用。
        """
        if not self.installed_path or not self.installed_path.exists():
            return None
        candidate = self.installed_path / skill_name
        return candidate if candidate.is_dir() else None

    def _find_source_dir(self, skill_name: str) -> Optional[Tuple[str, Path]]:
        """在所有 source_paths 中查找 Skill 源码目录，返回 (layer, path)"""
        for layer, src_root in sorted(self.source_paths.items(),
                                      key=lambda x: LAYER_PRIORITY.get(x[0], 99)):
            candidate = src_root / skill_name
            if candidate.is_dir():
                return layer, candidate
        return None

    def _get_tool_path(self, tool_name: str, layer: str = "user") -> Optional[Path]:
        """
        查找 Tool 的实际路径。

        路径规则：
        - 官方/市集 Tool：{project_root}/tools/{layer}/{dcc}/{name}/
          （官方/市集不复制，直接读 project_root；dcc 层由调用方通过 dcc 参数指定，
           此方法在所有 dcc 子目录下搜索）
        - 用户 Tool：~/.artclaw/tools/user/{name}/

        :param tool_name: Tool 名称
        :param layer: 层级（"official"/"marketplace"/"user"），默认 "user"
        :return: 找到的目录 Path，或 None
        """
        if layer == "user":
            candidate = Path("~/.artclaw/tools/user").expanduser() / tool_name
            return candidate if candidate.is_dir() else None
        # 官方/市集：在 project_root/tools/{layer}/ 下搜索所有 dcc 子目录
        if self._project_root:
            layer_root = self._project_root / "tools" / layer
            if layer_root.exists():
                # 在所有 dcc 子目录中搜索
                for dcc_dir in layer_root.iterdir():
                    if dcc_dir.is_dir():
                        candidate = dcc_dir / tool_name
                        if candidate.is_dir():
                            return candidate
        return None

    def _get_workflow_path(self, workflow_name: str, layer: str = "user") -> Optional[Path]:
        """
        查找 Workflow 的实际路径。

        路径规则与 Tool 相同，只是根目录改为 workflows/。
        - 官方/市集：{project_root}/workflows/{layer}/{dcc}/{name}/
        - 用户：~/.artclaw/workflows/user/{name}/
        """
        if layer == "user":
            candidate = Path("~/.artclaw/workflows/user").expanduser() / workflow_name
            return candidate if candidate.is_dir() else None
        if self._project_root:
            layer_root = self._project_root / "workflows" / layer
            if layer_root.exists():
                for dcc_dir in layer_root.iterdir():
                    if dcc_dir.is_dir():
                        candidate = dcc_dir / workflow_name
                        if candidate.is_dir():
                            return candidate
        return None

    # ── 版本查询 ──────────────────────────────────────────────────────────────

    def get_installed_version(self, skill_name: str) -> Optional[str]:
        """获取已安装 Skill 的版本号"""
        skill_dir = self._find_skill_dir(skill_name)
        if skill_dir:
            return _extract_version_from_dir(skill_dir)
        return None

    def check_skill_sync(self, skill_name: str) -> SyncStatus:
        """
        检查指定 Skill 的安装版本与源码版本的同步状态。
        """
        installed = self._find_skill_dir(skill_name)
        if not installed:
            return SyncStatus(state=SyncState.NOT_INSTALLED, skill_name=skill_name)
        source_info = self._find_source_dir(skill_name)
        source_dir = source_info[1] if source_info else None
        return compare_skill_dirs(installed, source_dir or Path(""))

    def check_all_sync(self) -> List[SyncStatus]:
        """检查所有已安装 Skill 的同步状态"""
        if not self.installed_path or not self.installed_path.exists():
            return []
        results = []
        for skill_dir in sorted(self.installed_path.iterdir()):
            if not skill_dir.is_dir():
                continue
            source_info = self._find_source_dir(skill_dir.name)
            source_dir = source_info[1] if source_info else None
            results.append(compare_skill_dirs(skill_dir, source_dir or Path("")))
        return results

    def check_dependencies(self, skill_dir: Path) -> List[str]:
        """
        检查 Skill 的依赖是否都已安装。

        :return: 缺失的依赖名称列表
        """
        manifest = self._read_manifest(skill_dir)
        if not manifest:
            return []
        missing = []
        for dep in manifest.get("dependencies", []):
            dep_name = re.split(r"[>=<]", dep)[0].strip()
            if "." in dep_name:
                dep_name = dep_name.split(".")[-1]
            if not self._find_skill_dir(dep_name):
                missing.append(dep)
        return missing

    # ── 安装操作 ──────────────────────────────────────────────────────────────

    def install(
        self,
        source_dir: Path,
        force: bool = False,
        install_deps: bool = True,
        source_layer: str = "",
    ) -> InstallResult:
        """
        安装 Skill 到 installed_path（扁平结构，OpenClaw 规范）。

        安装目标始终是 installed_path/{skill_name}/，没有层级子目录。
        层级（source_layer）仅用于记录 Skill 来源，不影响安装路径。

        :param source_dir:   Skill 源码目录（含 manifest.json 或 SKILL.md）
        :param force:        是否强制覆盖已有版本
        :param install_deps: 是否自动安装缺失依赖
        :param source_layer: 来源层级标识（"00_official"/"01_team"/"02_user"），仅用于日志/记录
        :return: InstallResult
        """
        source_dir = Path(source_dir).expanduser()
        if not source_dir.is_dir():
            return InstallResult(success=False, error=f"源目录不存在: {source_dir}")

        manifest = self._read_manifest(source_dir)
        skill_name = (manifest or {}).get("name") or source_dir.name
        version = (manifest or {}).get("version", "")

        if not self.installed_path:
            return InstallResult(success=False, error="未配置 installed_path")

        dest_dir = self.installed_path / skill_name

        if dest_dir.exists() and not force:
            return InstallResult(
                success=False,
                skill_name=skill_name,
                error=f"Skill '{skill_name}' 已安装，使用 force=True 覆盖",
            )

        try:
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(
                str(source_dir), str(dest_dir),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )
        except Exception as e:
            return InstallResult(success=False, skill_name=skill_name, error=str(e))

        # 自动安装依赖
        deps_installed: List[str] = []
        if install_deps:
            missing = self.check_dependencies(dest_dir)
            for dep_raw in missing:
                dep_name = re.split(r"[>=<]", dep_raw)[0].strip()
                if "." in dep_name:
                    dep_name = dep_name.split(".")[-1]
                src_info = self._find_source_dir(dep_name)
                if src_info:
                    dep_result = self.install(src_info[1],
                                               source_layer=src_info[0],
                                               force=force, install_deps=False)
                    if dep_result.success:
                        deps_installed.append(dep_name)

        return InstallResult(
            success=True,
            skill_name=skill_name,
            version=version,
            installed_to=str(dest_dir),
            deps_installed=deps_installed,
        )

    def uninstall(self, skill_name: str) -> Dict[str, Any]:
        """卸载已安装的 Skill"""
        skill_dir = self._find_skill_dir(skill_name)
        if not skill_dir:
            return {"success": False, "error": f"Skill '{skill_name}' 未安装"}
        try:
            shutil.rmtree(str(skill_dir))
            return {"success": True, "skill_name": skill_name}
        except Exception as e:
            return {"success": False, "skill_name": skill_name, "error": str(e)}

    # ── 发布操作 ──────────────────────────────────────────────────────────────

    def publish(
        self,
        skill_name: str,
        target_layer: str,
        message: str = "",
    ) -> PublishResult:
        """
        将已安装的 Skill 发布回源码端的指定层级。

        数据流：
          installed_path/{skill_name}/  →  source_paths[target_layer]/{skill_name}/

        安装目录是扁平的，发布时从扁平安装目录读取，写入源码端的分层目录。
        "from_layer" 通过检查源码端哪个层级有同名 Skill 来推断（仅用于日志）。

        :param skill_name:   要发布的 Skill 名称（须已安装）
        :param target_layer: 目标源码层级（如 "00_official" | "01_team"），需在 source_paths 中配置
        :param message:      发布说明（仅用于日志，不写入文件）
        :return: PublishResult
        """
        skill_dir = self._find_skill_dir(skill_name)
        if not skill_dir:
            return PublishResult(success=False, skill_name=skill_name,
                                  error=f"Skill '{skill_name}' 未安装")

        if target_layer not in self.source_paths:
            return PublishResult(success=False, skill_name=skill_name,
                                  error=f"目标层级 '{target_layer}' 未在 source_paths 中配置")

        target_root = self.source_paths[target_layer]
        target_dir = target_root / skill_name
        version = _extract_version_from_dir(skill_dir) or ""

        # 推断来源层级（仅用于日志/报告）
        from_layer = "installed"
        src_info = self._find_source_dir(skill_name)
        if src_info:
            from_layer = src_info[0]

        try:
            if target_dir.exists():
                shutil.rmtree(str(target_dir))
            shutil.copytree(
                str(skill_dir), str(target_dir),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )
            return PublishResult(
                success=True,
                skill_name=skill_name,
                from_layer=from_layer,
                to_layer=target_layer,
                version=version,
            )
        except Exception as e:
            return PublishResult(success=False, skill_name=skill_name, error=str(e))

    # ── 启用/禁用 ──────────────────────────────────────────────────────────────

    def get_disabled_skills(self) -> List[str]:
        """获取所有禁用的 Skill 名称列表"""
        return self._read_config().get("disabled_skills", [])

    def disable(self, skill_name: str) -> bool:
        """
        禁用 Skill（写入 config.json 的 disabled_skills 列表）。
        :return: True 表示已写入，False 表示已经是禁用状态
        """
        cfg = self._read_config()
        disabled = cfg.get("disabled_skills", [])
        if skill_name in disabled:
            return False
        disabled.append(skill_name)
        cfg["disabled_skills"] = disabled
        self._write_config(cfg)
        return True

    def enable(self, skill_name: str) -> bool:
        """
        启用 Skill（从 config.json 的 disabled_skills 移除）。
        :return: True 表示已移除，False 表示本来就不在禁用列表
        """
        cfg = self._read_config()
        disabled = cfg.get("disabled_skills", [])
        if skill_name not in disabled:
            return False
        disabled.remove(skill_name)
        cfg["disabled_skills"] = disabled
        self._write_config(cfg)
        return True

    # ── 冲突检测 ──────────────────────────────────────────────────────────────

    def detect_conflicts(self) -> List[ConflictInfo]:
        """检测所有 source_paths 中的层级命名冲突"""
        layer_skills: Dict[str, List[str]] = {}
        for layer, src_root in self.source_paths.items():
            if src_root.exists():
                layer_skills[layer] = [
                    d.name for d in src_root.iterdir() if d.is_dir()
                ]
        return detect_layer_conflicts(layer_skills)

    # ── Skill 匹配 ────────────────────────────────────────────────────────────

    def find_best_match(
        self,
        skill_name: str,
        software: str,
        software_version: str,
    ) -> Optional[Dict[str, Any]]:
        """
        在所有 source_paths 中查找最适合当前 DCC 版本的 Skill manifest。
        当同名 Skill 在多个层级都有时，用 version_distance 选最精确的。
        """
        candidates: List[Tuple[str, Path, Dict]] = []
        for layer, src_root in self.source_paths.items():
            candidate = src_root / skill_name
            if candidate.is_dir():
                m = self._read_manifest(candidate)
                if m and matches_skill(m, software, software_version):
                    candidates.append((layer, candidate, m))

        if not candidates:
            return None

        result = select_best_match(
            candidates,
            software,
            software_version,
            manifest_key=lambda x: x[2],
        )
        if result:
            return result[1][2]  # 返回 manifest 字典
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # Tool 管理
    # ══════════════════════════════════════════════════════════════════════════
    #
    # Tool 目录规范：
    #   官方/市集  → {project_root}/tools/{layer}/{dcc}/{name}/  （不复制，直接读）
    #   用户自建   → ~/.artclaw/tools/user/{name}/
    #
    # Tool 不需要"安装"动作；只有用户 Tool 支持 create/delete；
    # publish 将用户 Tool 提升到官方/市集层（复制后删除用户副本）。
    # ══════════════════════════════════════════════════════════════════════════

    def create_tool(
        self,
        source_dir: Path,
        dcc: str = "universal",
    ) -> Dict[str, Any]:
        """
        将一个 Tool 目录注册为用户 Tool（复制到 ~/.artclaw/tools/user/{name}/）。

        只有用户层 Tool 支持创建；官方/市集 Tool 直接放到 project_root，不走此接口。

        :param source_dir: Tool 源目录（含 manifest.json）
        :param dcc:        目标 DCC（仅用于 manifest 记录，不影响路径，用户层无 dcc 子目录）
        :return: {"success": bool, "tool_name": str, "path": str, "error": str|None}
        """
        source_dir = Path(source_dir).expanduser()
        if not source_dir.is_dir():
            return {"success": False, "error": f"源目录不存在: {source_dir}"}

        manifest = self._read_manifest(source_dir)
        tool_name = (manifest or {}).get("name") or source_dir.name

        dest = Path("~/.artclaw/tools/user").expanduser() / tool_name
        if dest.exists():
            return {"success": False, "tool_name": tool_name,
                    "error": f"Tool '{tool_name}' 已存在，使用 delete_tool() 先删除"}

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                str(source_dir), str(dest),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )
            return {"success": True, "tool_name": tool_name, "path": str(dest)}
        except Exception as e:
            return {"success": False, "tool_name": tool_name, "error": str(e)}

    def delete_tool(self, tool_name: str) -> Dict[str, Any]:
        """
        删除用户 Tool（只能删除 user 层，官方/市集 Tool 不可删除）。

        :param tool_name: Tool 名称
        :return: {"success": bool, "tool_name": str, "error": str|None}
        """
        tool_dir = self._get_tool_path(tool_name, layer="user")
        if not tool_dir:
            return {"success": False, "tool_name": tool_name,
                    "error": f"用户 Tool '{tool_name}' 不存在（官方/市集 Tool 不可删除）"}
        try:
            shutil.rmtree(str(tool_dir))
            return {"success": True, "tool_name": tool_name}
        except Exception as e:
            return {"success": False, "tool_name": tool_name, "error": str(e)}

    def publish_tool(
        self,
        tool_name: str,
        target_layer: str,
        dcc: str = "universal",
        version: str = "",
        message: str = "",
    ) -> PublishResult:
        """
        将用户 Tool 发布到官方/市集层（提升）。

        数据流：
          ~/.artclaw/tools/user/{name}/
            → {project_root}/tools/{target_layer}/{dcc}/{name}/
            → 删除用户副本

        :param tool_name:    要发布的 Tool 名称（须在用户层存在）
        :param target_layer: 目标层级（"official" 或 "marketplace"）
        :param dcc:          目标 DCC 子目录（如 "universal"/"unreal_engine"/"maya"）
        :param version:      发布版本号（留空则保持 manifest 中的版本）
        :param message:      发布说明（仅用于日志）
        :return: PublishResult
        """
        if target_layer not in ("official", "marketplace"):
            return PublishResult(success=False, skill_name=tool_name,
                                  error=f"target_layer 必须是 'official' 或 'marketplace'，got '{target_layer}'")

        src = self._get_tool_path(tool_name, layer="user")
        if not src:
            return PublishResult(success=False, skill_name=tool_name,
                                  error=f"用户 Tool '{tool_name}' 不存在")

        if not self._project_root:
            return PublishResult(success=False, skill_name=tool_name,
                                  error="未配置 project_root，无法发布到官方/市集层")

        dest = self._project_root / "tools" / target_layer / dcc / tool_name
        inst_ver = _extract_version_from_dir(src) or ""
        pub_ver = version or inst_ver

        try:
            if dest.exists():
                shutil.rmtree(str(dest))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                str(src), str(dest),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )
            # 更新目标 manifest 的 version 和 source 字段
            dest_manifest_path = dest / "manifest.json"
            if dest_manifest_path.exists() and pub_ver:
                try:
                    m = json.loads(dest_manifest_path.read_text(encoding="utf-8"))
                    m["version"] = pub_ver
                    m["source"] = target_layer
                    dest_manifest_path.write_text(
                        json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                except Exception:
                    pass
            # 发布成功后删除用户副本
            shutil.rmtree(str(src))
            return PublishResult(
                success=True,
                skill_name=tool_name,
                from_layer="user",
                to_layer=f"{target_layer}/{dcc}",
                version=pub_ver,
            )
        except Exception as e:
            return PublishResult(success=False, skill_name=tool_name, error=str(e))

    def list_tools(
        self,
        layer: Optional[str] = None,
        dcc: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出所有 Tool（官方、市集、用户层）。

        :param layer: 过滤层级（"official"/"marketplace"/"user"），None 返回全部
        :param dcc:   过滤 DCC（如 "universal"/"unreal_engine"），None 返回全部
        :return: 列表，每项包含 name/layer/dcc/path/version
        """
        results: List[Dict[str, Any]] = []

        def _scan_layer_root(root: Path, lname: str) -> None:
            if not root.exists():
                return
            if lname == "user":
                # 用户层：~/.artclaw/tools/user/{name}/（无 dcc 子目录）
                for item in sorted(root.iterdir()):
                    if not item.is_dir():
                        continue
                    if dcc and dcc != "universal":
                        continue  # 用户层视为 universal
                    m = self._read_manifest(item)
                    results.append({
                        "name": item.name,
                        "layer": lname,
                        "dcc": "universal",
                        "path": str(item),
                        "version": (m or {}).get("version", ""),
                    })
            else:
                # 官方/市集层：{layer}/{dcc}/{name}/
                for dcc_dir in sorted(root.iterdir()):
                    if not dcc_dir.is_dir():
                        continue
                    if dcc and dcc_dir.name != dcc:
                        continue
                    for item in sorted(dcc_dir.iterdir()):
                        if not item.is_dir():
                            continue
                        m = self._read_manifest(item)
                        results.append({
                            "name": item.name,
                            "layer": lname,
                            "dcc": dcc_dir.name,
                            "path": str(item),
                            "version": (m or {}).get("version", ""),
                        })

        layers_to_scan = [layer] if layer else ["official", "marketplace", "user"]
        for lname in layers_to_scan:
            if lname == "user":
                _scan_layer_root(
                    Path("~/.artclaw/tools/user").expanduser(), "user"
                )
            elif self._project_root:
                _scan_layer_root(
                    self._project_root / "tools" / lname, lname
                )

        return results

    def get_tool_version(self, tool_name: str, layer: str = "user") -> Optional[str]:
        """
        获取指定 Tool 的版本号。

        :param tool_name: Tool 名称
        :param layer:     层级（默认 "user"）
        :return: 版本字符串，或 None
        """
        tool_dir = self._get_tool_path(tool_name, layer=layer)
        if tool_dir:
            return _extract_version_from_dir(tool_dir)
        return None

    def check_tool_sync(self, tool_name: str) -> SyncStatus:
        """
        检查用户 Tool 与项目仓库（官方/市集）中同名 Tool 的同步状态。

        用于判断用户 Tool 是否可以/应该发布。

        :param tool_name: Tool 名称
        :return: SyncStatus
        """
        user_dir = self._get_tool_path(tool_name, layer="user")
        if not user_dir:
            return SyncStatus(state=SyncState.NOT_INSTALLED, skill_name=tool_name)
        # 在 official/marketplace 中搜索同名
        repo_dir: Optional[Path] = None
        for lname in ("official", "marketplace"):
            candidate = self._get_tool_path(tool_name, layer=lname)
            if candidate:
                repo_dir = candidate
                break
        return compare_skill_dirs(user_dir, repo_dir or Path(""))

    # ══════════════════════════════════════════════════════════════════════════
    # Workflow 管理
    # ══════════════════════════════════════════════════════════════════════════
    #
    # Workflow 目录规范（与 Tool 相同）：
    #   官方/市集  → {project_root}/workflows/{layer}/{dcc}/{name}/  （不复制，直接读）
    #   用户自建   → ~/.artclaw/workflows/user/{name}/
    #
    # 额外：部分 Skill 内嵌 workflow.json，跟随 Skill 安装到
    #       {skills_installed_path}/{skill_name}/workflow.json
    # ══════════════════════════════════════════════════════════════════════════

    def create_workflow(
        self,
        source_dir: Path,
        dcc: str = "universal",
    ) -> Dict[str, Any]:
        """
        将一个 Workflow 目录注册为用户 Workflow（复制到 ~/.artclaw/workflows/user/{name}/）。

        :param source_dir: Workflow 源目录（含 manifest.json 或 workflow.json）
        :param dcc:        目标 DCC（仅用于记录，用户层无 dcc 子目录）
        :return: {"success": bool, "workflow_name": str, "path": str, "error": str|None}
        """
        source_dir = Path(source_dir).expanduser()
        if not source_dir.is_dir():
            return {"success": False, "error": f"源目录不存在: {source_dir}"}

        manifest = self._read_manifest(source_dir)
        workflow_name = (manifest or {}).get("name") or source_dir.name

        dest = Path("~/.artclaw/workflows/user").expanduser() / workflow_name
        if dest.exists():
            return {"success": False, "workflow_name": workflow_name,
                    "error": f"Workflow '{workflow_name}' 已存在"}

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                str(source_dir), str(dest),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )
            return {"success": True, "workflow_name": workflow_name, "path": str(dest)}
        except Exception as e:
            return {"success": False, "workflow_name": workflow_name, "error": str(e)}

    def delete_workflow(self, workflow_name: str) -> Dict[str, Any]:
        """
        删除用户 Workflow（只能删除 user 层，官方/市集不可删除）。
        """
        wf_dir = self._get_workflow_path(workflow_name, layer="user")
        if not wf_dir:
            return {"success": False, "workflow_name": workflow_name,
                    "error": f"用户 Workflow '{workflow_name}' 不存在"}
        try:
            shutil.rmtree(str(wf_dir))
            return {"success": True, "workflow_name": workflow_name}
        except Exception as e:
            return {"success": False, "workflow_name": workflow_name, "error": str(e)}

    def publish_workflow(
        self,
        workflow_name: str,
        target_layer: str,
        dcc: str = "universal",
        version: str = "",
        message: str = "",
    ) -> PublishResult:
        """
        将用户 Workflow 发布到官方/市集层（提升）。

        数据流：
          ~/.artclaw/workflows/user/{name}/
            → {project_root}/workflows/{target_layer}/{dcc}/{name}/
            → 删除用户副本

        :param workflow_name: 要发布的 Workflow 名称（须在用户层存在）
        :param target_layer:  目标层级（"official" 或 "marketplace"）
        :param dcc:           目标 DCC 子目录
        :param version:       发布版本号（留空则保持现有版本）
        :param message:       发布说明（仅用于日志）
        """
        if target_layer not in ("official", "marketplace"):
            return PublishResult(success=False, skill_name=workflow_name,
                                  error=f"target_layer 必须是 'official' 或 'marketplace'")

        src = self._get_workflow_path(workflow_name, layer="user")
        if not src:
            return PublishResult(success=False, skill_name=workflow_name,
                                  error=f"用户 Workflow '{workflow_name}' 不存在")

        if not self._project_root:
            return PublishResult(success=False, skill_name=workflow_name,
                                  error="未配置 project_root，无法发布")

        dest = self._project_root / "workflows" / target_layer / dcc / workflow_name
        inst_ver = _extract_version_from_dir(src) or ""
        pub_ver = version or inst_ver

        try:
            if dest.exists():
                shutil.rmtree(str(dest))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                str(src), str(dest),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )
            # 更新 manifest
            dest_manifest_path = dest / "manifest.json"
            if dest_manifest_path.exists() and pub_ver:
                try:
                    m = json.loads(dest_manifest_path.read_text(encoding="utf-8"))
                    m["version"] = pub_ver
                    m["source"] = target_layer
                    dest_manifest_path.write_text(
                        json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                except Exception:
                    pass
            shutil.rmtree(str(src))
            return PublishResult(
                success=True,
                skill_name=workflow_name,
                from_layer="user",
                to_layer=f"{target_layer}/{dcc}",
                version=pub_ver,
            )
        except Exception as e:
            return PublishResult(success=False, skill_name=workflow_name, error=str(e))

    def list_workflows(
        self,
        layer: Optional[str] = None,
        dcc: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出所有 Workflow（官方、市集、用户层）。

        :param layer: 过滤层级（"official"/"marketplace"/"user"），None 返回全部
        :param dcc:   过滤 DCC，None 返回全部
        :return: 列表，每项包含 name/layer/dcc/path/version
        """
        results: List[Dict[str, Any]] = []

        def _scan(root: Path, lname: str) -> None:
            if not root.exists():
                return
            if lname == "user":
                for item in sorted(root.iterdir()):
                    if not item.is_dir():
                        continue
                    m = self._read_manifest(item)
                    results.append({
                        "name": item.name, "layer": lname,
                        "dcc": "universal", "path": str(item),
                        "version": (m or {}).get("version", ""),
                    })
            else:
                for dcc_dir in sorted(root.iterdir()):
                    if not dcc_dir.is_dir():
                        continue
                    if dcc and dcc_dir.name != dcc:
                        continue
                    for item in sorted(dcc_dir.iterdir()):
                        if not item.is_dir():
                            continue
                        m = self._read_manifest(item)
                        results.append({
                            "name": item.name, "layer": lname,
                            "dcc": dcc_dir.name, "path": str(item),
                            "version": (m or {}).get("version", ""),
                        })

        layers_to_scan = [layer] if layer else ["official", "marketplace", "user"]
        for lname in layers_to_scan:
            if lname == "user":
                _scan(Path("~/.artclaw/workflows/user").expanduser(), "user")
            elif self._project_root:
                _scan(self._project_root / "workflows" / lname, lname)

        return results

    def get_workflow_version(self, workflow_name: str, layer: str = "user") -> Optional[str]:
        """
        获取指定 Workflow 的版本号。

        :param workflow_name: Workflow 名称
        :param layer:         层级（默认 "user"）
        """
        wf_dir = self._get_workflow_path(workflow_name, layer=layer)
        if wf_dir:
            return _extract_version_from_dir(wf_dir)
        return None

    def check_workflow_sync(self, workflow_name: str) -> SyncStatus:
        """
        检查用户 Workflow 与仓库中同名 Workflow 的同步状态。
        """
        user_dir = self._get_workflow_path(workflow_name, layer="user")
        if not user_dir:
            return SyncStatus(state=SyncState.NOT_INSTALLED, skill_name=workflow_name)
        repo_dir: Optional[Path] = None
        for lname in ("official", "marketplace"):
            candidate = self._get_workflow_path(workflow_name, layer=lname)
            if candidate:
                repo_dir = candidate
                break
        return compare_skill_dirs(user_dir, repo_dir or Path(""))
