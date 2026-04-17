# DCCClawBridge adapters package
from .base_adapter import BaseDCCAdapter

__all__ = ["BaseDCCAdapter"]

# Lazy imports — only import specific adapter when needed
# from .maya_adapter import MayaAdapter
# from .max_adapter import MaxAdapter
# from .blender_adapter import BlenderAdapter
# from .houdini_adapter import HoudiniAdapter
# from .substance_painter_adapter import SubstancePainterAdapter
# from .substance_designer_adapter import SubstanceDesignerAdapter

# UEAdapter: unreal 模块只在 Unreal Engine Python 运行时中可用
try:
    from .ue_adapter import UEAdapter
    __all__ = __all__ + ["UEAdapter"]
except ImportError:
    pass
