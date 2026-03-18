"""
test_phase_b.py - Phase B 模块单元测试
=========================================

测试 skill_manifest, skill_version, skill_conflict 模块。
不依赖 unreal 模块，可在普通 Python 环境下运行。

用法:
    python test_phase_b.py
"""

import json
import os
import sys
import tempfile
import shutil

# 将模块目录加入 path
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)


# ============================================================================
# Test skill_manifest.py
# ============================================================================

def test_manifest_parsing():
    """测试 manifest 解析"""
    from skill_manifest import parse_manifest, validate_manifest, SkillManifest

    # 创建临时测试 manifest
    tmpdir = tempfile.mkdtemp(prefix="artclaw_test_")
    try:
        # 有效 manifest
        manifest_data = {
            "manifest_version": "1.0",
            "name": "test_skill",
            "display_name": "Test Skill",
            "description": "A test skill for unit testing",
            "version": "1.0.0",
            "author": "TestAuthor",
            "software": "unreal_engine",
            "software_version": {"min": "5.1", "max": "5.5"},
            "category": "utils",
            "risk_level": "low",
            "entry_point": "__init__.py",
            "tools": [
                {"name": "test_tool", "description": "A test tool"}
            ],
            "tags": ["test", "unit-test"],
        }
        manifest_path = os.path.join(tmpdir, "manifest.json")
        init_path = os.path.join(tmpdir, "__init__.py")

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)
        with open(init_path, "w") as f:
            f.write("# test\n")

        # 解析
        manifest, errors = parse_manifest(manifest_path)
        assert manifest is not None, f"Parse failed: {[str(e) for e in errors]}"
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"
        assert manifest.software == "unreal_engine"
        assert manifest.category == "utils"
        assert len(manifest.tools) == 1
        assert manifest.tools[0].name == "test_tool"
        assert manifest.software_version is not None
        assert manifest.software_version.min_version == "5.1"
        assert manifest.software_version.max_version == "5.5"

        error_count = sum(1 for e in errors if e.severity == "error")
        assert error_count == 0, f"Unexpected errors: {[str(e) for e in errors]}"

        # 验证
        is_valid, verr = validate_manifest(manifest_path)
        assert is_valid, f"Validation failed: {[str(e) for e in verr]}"

        print("  [PASS] Valid manifest parsing")

        # 测试 to_dict
        d = manifest.to_dict()
        assert d["name"] == "test_skill"
        assert d["software_version"]["min"] == "5.1"
        print("  [PASS] to_dict()")

        # 测试无效 manifest
        invalid_data = {"manifest_version": "1.0"}  # 缺少必需字段
        with open(manifest_path, "w") as f:
            json.dump(invalid_data, f)

        _, errors = parse_manifest(manifest_path)
        error_count = sum(1 for e in errors if e.severity == "error")
        assert error_count > 0, "Expected validation errors for incomplete manifest"
        print(f"  [PASS] Invalid manifest detection ({error_count} errors)")

        # 测试无效 name 格式
        bad_name_data = dict(manifest_data)
        bad_name_data["name"] = "InvalidName"  # CamelCase not allowed
        with open(manifest_path, "w") as f:
            json.dump(bad_name_data, f)

        _, errors = parse_manifest(manifest_path)
        name_errors = [e for e in errors if e.field == "name" and e.severity == "error"]
        assert len(name_errors) > 0, "Expected name validation error"
        print("  [PASS] Invalid name detection")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_version_module():
    """测试 skill_version.py"""
    from skill_version import (
        parse_version, version_gte, version_lte,
        matches_software_version, version_distance, select_best_match,
    )
    from skill_manifest import SoftwareVersion, SkillManifest, ToolEntry

    # parse_version
    assert parse_version("5.4") == (5, 4)
    assert parse_version("5.4.1") == (5, 4, 1)
    assert parse_version("2024.3") == (2024, 3)
    assert parse_version("5.4.1-preview") == (5, 4, 1)
    assert parse_version("") == (0,)
    print("  [PASS] parse_version()")

    # version comparisons
    assert version_gte("5.4", "5.3")
    assert version_gte("5.4", "5.4")
    assert not version_gte("5.3", "5.4")
    assert version_lte("5.3", "5.4")
    print("  [PASS] version comparisons")

    # matches_software_version
    sv = SoftwareVersion(min_version="5.1", max_version="5.5")
    assert matches_software_version(sv, "5.3")
    assert matches_software_version(sv, "5.1")
    assert matches_software_version(sv, "5.5")
    assert not matches_software_version(sv, "5.0")
    assert not matches_software_version(sv, "5.6")
    assert matches_software_version(None, "5.3")  # no restriction
    print("  [PASS] matches_software_version()")

    # version_distance
    assert version_distance(sv, "5.3") < float("inf")
    assert version_distance(sv, "6.0") == float("inf")  # out of range
    assert version_distance(None, "5.3") == 100.0  # no restriction = low priority
    print("  [PASS] version_distance()")

    # select_best_match
    m1 = SkillManifest(
        name="test", software="unreal_engine",
        software_version=SoftwareVersion(min_version="5.3", max_version="5.5"),
        tools=[ToolEntry(name="t", description="d")],
    )
    m2 = SkillManifest(
        name="test", software="universal",
        tools=[ToolEntry(name="t", description="d")],
    )
    best = select_best_match([m1, m2], "unreal_engine", "5.4")
    assert best is m1, "Should prefer exact software match"
    print("  [PASS] select_best_match()")


def test_conflict_module():
    """测试 skill_conflict.py"""
    from skill_conflict import ConflictDetector, LAYER_PRIORITY
    from skill_manifest import SkillManifest, ToolEntry

    # 创建测试 manifest
    m_official = SkillManifest(
        name="my_skill", version="1.0.0",
        source_layer="official",
        tools=[ToolEntry(name="my_tool", description="d")],
    )
    m_user = SkillManifest(
        name="my_skill", version="2.0.0",
        source_layer="user",
        tools=[ToolEntry(name="my_tool", description="d")],
    )
    m_other = SkillManifest(
        name="other_skill", version="1.0.0",
        source_layer="team",
        tools=[ToolEntry(name="other_tool", description="d")],
    )

    detector = ConflictDetector()

    # 检测冲突
    report = detector.detect([m_official, m_user, m_other])
    assert report.has_conflicts
    assert len(report.skill_conflicts) == 1
    assert report.skill_conflicts[0].winner is m_official  # official wins
    print("  [PASS] Skill conflict detection")

    # 解决冲突
    resolved = detector.resolve([m_official, m_user, m_other])
    assert len(resolved) == 2
    names = [m.name for m in resolved]
    assert "my_skill" in names
    assert "other_skill" in names
    # 确认 winner 是 official 版本
    my = [m for m in resolved if m.name == "my_skill"][0]
    assert my.source_layer == "official"
    print("  [PASS] Conflict resolution")

    # Tool 冲突 (不同 Skill 暴露同名 Tool)
    m_a = SkillManifest(
        name="skill_a", source_layer="official",
        tools=[ToolEntry(name="shared_tool", description="d")],
    )
    m_b = SkillManifest(
        name="skill_b", source_layer="team",
        tools=[ToolEntry(name="shared_tool", description="d")],
    )
    report2 = detector.detect([m_a, m_b])
    assert len(report2.tool_conflicts) == 1
    assert report2.tool_conflicts[0].tool_name == "shared_tool"
    print("  [PASS] Tool conflict detection")

    # 禁用 Skill
    detector_disabled = ConflictDetector(disabled_skills={"my_skill"})
    resolved2 = detector_disabled.resolve([m_official, m_user, m_other])
    names2 = [m.name for m in resolved2]
    assert "my_skill" not in names2
    assert "other_skill" in names2
    print("  [PASS] Disabled skill exclusion")

    # Report serialization
    d = report.to_dict()
    assert d["has_conflicts"] is True
    assert d["total_conflicts"] >= 1
    print("  [PASS] Report serialization")


# ============================================================================
# 运行
# ============================================================================

if __name__ == "__main__":
    print("\n=== Phase B Unit Tests ===\n")

    print("[1/3] Testing skill_manifest...")
    test_manifest_parsing()

    print("\n[2/3] Testing skill_version...")
    test_version_module()

    print("\n[3/3] Testing skill_conflict...")
    test_conflict_module()

    print("\n=== All Phase B tests passed! ===\n")
