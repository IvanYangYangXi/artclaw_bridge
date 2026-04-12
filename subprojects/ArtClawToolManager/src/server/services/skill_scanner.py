# Ref: docs/features/phase2-skill-management.md#SkillScanner
"""
Scan ``~/.openclaw/skills/`` for installed skills by reading SKILL.md
frontmatter.

Each skill directory is expected to have a ``SKILL.md`` with YAML
frontmatter (delimited by ``---``).  The scanner extracts:
  - name
  - description
  - metadata.artclaw.version
  - metadata.artclaw.dcc  (single string → list)
  - metadata.artclaw.author
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..core.config import settings


@dataclass
class ScannedSkill:
    """Parsed information from a single skill directory."""
    name: str
    description: str = ""
    version: str = "0.0.0"
    author: str = ""
    updated_at: str = ""
    target_dccs: List[str] = field(default_factory=list)
    skill_path: str = ""
    source: str = ""  # official / marketplace / user (from frontmatter or heuristic)
    source_path: str = ""  # path to source directory in project repo
    sync_status: str = "no_source"  # synced/source_newer/installed_newer/conflict/no_source


# Minimal YAML-like parser – avoids a PyYAML dependency.

_FRONT_MATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---", re.DOTALL
)


def _parse_frontmatter(text: str) -> Dict[str, str]:
    """Very small YAML-subset parser (flat keys only, plus simple nesting)."""
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    result: Dict[str, str] = {}
    current_key: Optional[str] = None
    multi_line_buf: List[str] = []

    for line in block.splitlines():
        stripped = line.strip()
        # Detect key: value
        kv = re.match(r"^(\w[\w\.\-]*):\s*(.*)", line)
        if kv and not line.startswith(" " * 4):
            # Flush previous multiline
            if current_key and multi_line_buf:
                result[current_key] = " ".join(multi_line_buf).strip()
                multi_line_buf = []
            key = kv.group(1)
            val = kv.group(2).strip()
            if val == ">" or val == "|":
                current_key = key
                multi_line_buf = []
            else:
                result[key] = val.strip('"').strip("'")
                current_key = None
        elif current_key:
            if stripped:
                multi_line_buf.append(stripped)

    # Flush last
    if current_key and multi_line_buf:
        result[current_key] = " ".join(multi_line_buf).strip()

    return result


def _extract_nested(text: str, prefix: str) -> Dict[str, str]:
    """Extract indented keys under a parent key block."""
    result: Dict[str, str] = {}
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return result
    block = m.group(1)
    inside = False
    for line in block.splitlines():
        if re.match(rf"^{prefix}:\s*$", line.rstrip()):
            inside = True
            continue
        if inside:
            if line and not line[0].isspace():
                break
            kv = re.match(r"^\s+(\w[\w\-]*):\s*(.*)", line)
            if kv:
                result[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return result


def _parse_skill_md(skill_dir: Path) -> Optional[ScannedSkill]:
    """Parse a SKILL.md and return a ScannedSkill or None."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception:
        return None

    fm = _parse_frontmatter(text)
    if not fm.get("name"):
        return None

    # Try to read nested metadata.artclaw fields
    artclaw = _extract_nested(text, "    artclaw")
    # Fallback: look for top-level metadata block
    if not artclaw:
        metadata_block = _extract_nested(text, "metadata")
        # Could be metadata → artclaw nesting; try deeper
        # Simple heuristic: search for version/dcc/author at any indent
        artclaw = {}
        m2 = _FRONT_MATTER_RE.match(text)
        if m2:
            for line in m2.group(1).splitlines():
                kv = re.match(r"^\s+(?:artclaw:)?\s*(version|dcc|author|software|source|updated_at):\s*(.*)", line)
                if kv:
                    artclaw[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")

    version = artclaw.get("version", "0.0.0")
    author = artclaw.get("author", "")
    updated_at = artclaw.get("updated_at", "")
    
    # Fallback to manifest.json if version or author are missing/default
    if version == "0.0.0" or author == "":
        manifest_file = skill_dir / "manifest.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                if version == "0.0.0" and manifest.get("version"):
                    version = manifest["version"]
                if author == "" and manifest.get("author"):
                    author = manifest["author"]
            except Exception:
                pass  # Keep original values on error
    
    # Fallback to SKILL.md file mtime if updated_at is missing
    if not updated_at:
        try:
            mtime = skill_md.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(mtime)
            updated_at = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            updated_at = ""
    dcc_raw = artclaw.get("dcc", "")
    # dcc may be comma-separated or a single value
    dccs = [d.strip() for d in dcc_raw.split(",") if d.strip()] if dcc_raw else []

    # Also check 'software' field (some SKILL.md use this instead of 'dcc')
    if not dccs:
        software_raw = artclaw.get("software", "")
        if software_raw:
            mapped = _SOFTWARE_TO_DCC.get(software_raw.lower().strip(), software_raw.lower().strip())
            dccs = [mapped]

    # Fallback: infer DCC from skill name prefix
    if not dccs:
        dccs = _infer_dccs_from_name(fm["name"])

    # Source: from frontmatter or heuristic
    source = artclaw.get("source", "") or fm.get("source", "")
    if not source:
        source = _guess_source(fm["name"])

    return ScannedSkill(
        name=fm["name"],
        description=fm.get("description", ""),
        version=version,
        author=author,
        updated_at=updated_at,
        target_dccs=dccs,
        skill_path=str(skill_dir),
        source=source,
    )


# software field → standard DCC id mapping
_SOFTWARE_TO_DCC = {
    "unreal_engine": "ue57",
    "ue": "ue57",
    "ue5": "ue57",
    "maya": "maya2024",
    "3ds_max": "max2024",
    "3dsmax": "max2024",
    "blender": "blender",
    "houdini": "houdini",
    "substance_painter": "sp",
    "substance_designer": "sd",
    "comfyui": "comfyui",
}

# Skill name prefix → DCC id mapping (fallback when no dcc/software in frontmatter)
_NAME_PREFIX_TO_DCC = {
    "ue57": "ue57",
    "blender-": "blender",
    "maya-": "maya2024",
    "max-": "max2024",
    "comfyui-": "comfyui",
    "sp-": "sp",
    "sd-": "sd",
    "houdini-": "houdini",
    "generate-material": "ue57",
    "get-material": "ue57",
}

# Skills that are truly cross-DCC (general purpose)
_GENERAL_SKILLS = {
    "artclaw-knowledge", "artclaw-memory", "artclaw-skill-manage",
    "artclaw-tool-creator", "subagent-manager", "web-fetch",
    "scene-vision-analyzer",
}

# Explicit overrides for skills whose name prefix is misleading
_NAME_DCC_OVERRIDES = {
    "artclaw-material": ["ue57"],
}


def _infer_dccs_from_name(name: str) -> List[str]:
    """Infer DCC from skill name prefix. Returns ['general'] for cross-DCC skills."""
    low = name.lower()
    # Explicit overrides first
    if low in _NAME_DCC_OVERRIDES:
        return _NAME_DCC_OVERRIDES[low]
    if low in _GENERAL_SKILLS:
        return ["general"]
    for prefix, dcc_id in _NAME_PREFIX_TO_DCC.items():
        if low.startswith(prefix):
            return [dcc_id]
    return ["general"]  # Unknown → general


# Known official skill name prefixes
_OFFICIAL_PREFIXES = (
    "ue57", "blender-", "maya-", "max-", "comfyui-", "sp-", "sd-",
    "artclaw-", "scene-vision", "web-fetch", "subagent-",
)


def _guess_source(name: str) -> str:
    """Heuristic source classification based on skill name."""
    low = name.lower()
    for prefix in _OFFICIAL_PREFIXES:
        if low.startswith(prefix):
            return "official"
    if low.startswith("my-") or low.startswith("custom-"):
        return "user"
    return "marketplace"


def scan_skills(skills_dir: Optional[Path] = None) -> List[ScannedSkill]:
    """Scan the skills directory and return all discovered skills."""
    root = skills_dir or settings.skills_path
    if not root.exists():
        return []

    results: List[ScannedSkill] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        parsed = _parse_skill_md(child)
        if parsed is not None:
            results.append(parsed)

    # Build source path map from project repo
    source_map = _scan_source_directories()
    for skill in results:
        src_path = source_map.get(skill.name, "")
        if src_path:
            skill.source_path = src_path
            skill.sync_status = _compare_directories(
                Path(skill.skill_path), Path(src_path)
            )
        else:
            skill.source_path = ""
            skill.sync_status = "no_source"

    return results


# ------------------------------------------------------------------
# Source directory scanning & sync detection
# ------------------------------------------------------------------

def _scan_source_directories() -> Dict[str, str]:
    """Scan project_root/skills/ for source skill directories.

    Returns a map of {skill_name: source_dir_path}.
    Source tree structure: skills/{layer}/{dcc}/{skill_dir}/SKILL.md
    """
    from ..services.config_manager import ConfigManager
    cfg = ConfigManager().load()
    project_root = cfg.get("project_root", "")
    if not project_root:
        return {}

    skills_root = Path(project_root) / "skills"
    if not skills_root.exists():
        return {}

    result: Dict[str, str] = {}
    # Walk: skills/{layer}/{dcc}/{skill_dir}/SKILL.md
    for layer_dir in skills_root.iterdir():
        if not layer_dir.is_dir():
            continue
        for dcc_dir in layer_dir.iterdir():
            if not dcc_dir.is_dir():
                continue
            for skill_dir in dcc_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                try:
                    text = skill_md.read_text(encoding="utf-8")
                except Exception:
                    continue
                fm = _parse_frontmatter(text)
                name = fm.get("name", "")
                if name:
                    result[name] = str(skill_dir)

    return result


def _file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()


_SKIP_NAMES = {"__pycache__", ".git", ".DS_Store", "Thumbs.db"}


def _should_skip_part(part_name: str) -> bool:
    """Check if a path component should be skipped during sync comparison."""
    return part_name in _SKIP_NAMES or part_name.endswith(".pyc")


def _collect_file_hashes(root: Path) -> Dict[str, str]:
    """Collect relative-path → hash for all files under root, skipping __pycache__ etc."""
    hashes: Dict[str, str] = {}
    if not root.exists():
        return hashes
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root)
        if any(_should_skip_part(part) for part in rel.parts):
            continue
        rel_str = str(rel).replace("\\", "/")
        hashes[rel_str] = _file_hash(p)
    return hashes


def _compare_directories(installed: Path, source: Path) -> str:
    """Compare installed and source directories.

    Returns: 'synced' | 'source_newer' | 'installed_newer' | 'conflict'
    """
    if not installed.exists() or not source.exists():
        return "no_source"

    installed_hashes = _collect_file_hashes(installed)
    source_hashes = _collect_file_hashes(source)

    if installed_hashes == source_hashes:
        return "synced"

    # Check which side has differences
    all_files = set(installed_hashes.keys()) | set(source_hashes.keys())
    source_only_or_newer = False
    installed_only_or_newer = False

    for f in all_files:
        ih = installed_hashes.get(f, "")
        sh = source_hashes.get(f, "")
        if ih != sh:
            if not ih:
                # File exists only in source
                source_only_or_newer = True
            elif not sh:
                # File exists only in installed
                installed_only_or_newer = True
            else:
                # Both exist but differ – check mtime to guess direction
                installed_file = installed / f.replace("/", "\\") if "\\" in str(installed) else installed / f
                source_file = source / f.replace("/", "\\") if "\\" in str(source) else source / f
                try:
                    i_mtime = installed_file.stat().st_mtime
                    s_mtime = source_file.stat().st_mtime
                    if s_mtime > i_mtime:
                        source_only_or_newer = True
                    elif i_mtime > s_mtime:
                        installed_only_or_newer = True
                    else:
                        # Same mtime but different hash – conflict
                        source_only_or_newer = True
                        installed_only_or_newer = True
                except Exception:
                    source_only_or_newer = True
                    installed_only_or_newer = True

    if source_only_or_newer and installed_only_or_newer:
        return "conflict"
    elif source_only_or_newer:
        return "source_newer"
    elif installed_only_or_newer:
        return "installed_newer"
    return "synced"
