"""
skill_create_gameobject.py - 创建 GameObject Skill
====================================================

P0 核心 Skill：在 Unity 场景中创建 GameObject。
"""

from artclaw import skill, SkillResult


@skill(
    name="unity_create_gameobject",
    description="在当前 Unity 场景中创建一个 GameObject，可选指定名称、位置、旋转",
    category="gameobject",
    dcc="unity",
    params={
        "name": {"type": "string", "required": False, "default": "NewGameObject",
                 "description": "GameObject 名称"},
        "position": {"type": "vec3", "required": False, "default": [0, 0, 0],
                     "description": "世界坐标位置 [x, y, z]"},
        "rotation": {"type": "vec3", "required": False, "default": [0, 0, 0],
                     "description": "欧拉角旋转 [x, y, z]（度）"},
        "parent": {"type": "string", "required": False, "default": None,
                   "description": "父 GameObject 名称（可选）"},
    },
)
def unity_create_gameobject(
    name: str = "NewGameObject",
    position=(0, 0, 0),
    rotation=(0, 0, 0),
    parent: str = None,
) -> SkillResult:
    """在 Unity 场景中创建 GameObject"""
    px, py, pz = position
    rx, ry, rz = rotation
    parent_code = f'GameObject.Find("{parent}")' if parent else "null"

    code = f"""
import json
import UnityEngine

go = UnityEngine.GameObject("{name}")
go.transform.position = UnityEngine.Vector3({px}f, {py}f, {pz}f)
go.transform.eulerAngles = UnityEngine.Vector3({rx}f, {ry}f, {rz}f)

parent_go = {parent_code}
if parent_go is not None:
    go.transform.SetParent(parent_go.transform, True)

# 记录 Undo
UnityEditor.Undo.RegisterCreatedObjectUndo(go, "ArtClaw 创建 GameObject")

result = {{
    "name": go.name,
    "instance_id": go.GetInstanceID(),
    "position": [go.transform.position.x, go.transform.position.y, go.transform.position.z],
}}
print(json.dumps(result))
"""
    import json
    from unity_adapter import UnityAdapter

    adapter = UnityAdapter()
    exec_result = adapter.execute_code(code)

    if not exec_result.get("success"):
        return SkillResult.error(f"创建 GameObject 失败: {exec_result.get('error')}")

    try:
        data = json.loads(exec_result.get("output", exec_result.get("result", "{}")))
        return SkillResult.success(data)
    except json.JSONDecodeError as e:
        return SkillResult.error(f"解析响应失败: {e}")
