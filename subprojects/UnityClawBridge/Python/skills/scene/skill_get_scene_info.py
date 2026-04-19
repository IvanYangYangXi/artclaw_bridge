"""
skill_get_scene_info.py - Unity 场景信息查询 Skill
==================================================

P0 核心 Skill：获取当前 Unity 场景的摘要信息。
AI 通过 run_unity_python 调用此 Skill。
"""

from artclaw import skill, SkillResult


@skill(
    name="unity_get_scene_info",
    description="获取当前 Unity 场景的基本信息（场景名、GameObject 数量、文件路径等）",
    category="scene",
    dcc="unity",
    params={},
)
def unity_get_scene_info() -> SkillResult:
    """
    查询 Unity 当前活动场景信息。
    
    Unity API（C#）等效代码：
      UnityEngine.SceneManagement.SceneManager.GetActiveScene()
    
    Returns:
        SkillResult 包含 scene_name, object_count, file_path, is_dirty 字段
    """
    # 通过 CommandServer 在 Unity 主线程执行
    code = """
import json
import UnityEngine.SceneManagement as SM
import UnityEngine

scene = SM.SceneManager.GetActiveScene()

# 递归计算所有 GameObject 数量
def count_all_objects(root_objects):
    count = 0
    for obj in root_objects:
        count += 1
        count += count_all_objects(obj.transform)
    return count

root_objects = scene.GetRootGameObjects()
total_objects = count_all_objects(root_objects)

result = {
    "scene_name": scene.name,
    "file_path": scene.path,
    "root_object_count": scene.rootCount,
    "total_object_count": total_objects,
    "is_dirty": scene.isDirty,
    "is_loaded": scene.isLoaded,
    "build_index": scene.buildIndex,
}
print(json.dumps(result))
"""
    import json
    from unity_adapter import UnityAdapter

    adapter = UnityAdapter()
    exec_result = adapter.execute_code(code)

    if not exec_result.get("success"):
        return SkillResult.error(f"查询场景信息失败: {exec_result.get('error')}")

    try:
        data = json.loads(exec_result.get("output", exec_result.get("result", "{}")))
        return SkillResult.success(data)
    except json.JSONDecodeError as e:
        return SkillResult.error(f"解析响应失败: {e}")
