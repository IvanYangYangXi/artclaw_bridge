"""
ArtClaw Standard Skill Categories
===================================
Canonical category definitions for all ArtClaw skills.
"""

# P0 Core categories
SCENE = "scene"
ASSET = "asset"
MATERIAL = "material"
LIGHTING = "lighting"
RENDER = "render"
BLUEPRINT = "blueprint"
ANIMATION = "animation"
UI = "ui"

# P1 Extended categories
UTILS = "utils"
INTEGRATION = "integration"
WORKFLOW = "workflow"

# All valid categories
ALL_CATEGORIES = {
    SCENE, ASSET, MATERIAL, LIGHTING, RENDER,
    BLUEPRINT, ANIMATION, UI,
    UTILS, INTEGRATION, WORKFLOW,
}

# Category display names (Chinese)
CATEGORY_DISPLAY = {
    SCENE: "场景操作",
    ASSET: "资产管理",
    MATERIAL: "材质编辑",
    LIGHTING: "灯光设置",
    RENDER: "渲染设置",
    BLUEPRINT: "蓝图操作",
    ANIMATION: "动画相关",
    UI: "UI/UMG",
    UTILS: "工具类",
    INTEGRATION: "第三方集成",
    WORKFLOW: "工作流自动化",
}

# Risk levels
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

ALL_RISK_LEVELS = {RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_CRITICAL}
