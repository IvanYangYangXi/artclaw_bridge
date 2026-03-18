# DCCClawBridge adapters package
from .base_adapter import BaseDCCAdapter

__all__ = ["BaseDCCAdapter"]

# Lazy imports — only import specific adapter when needed
# from .maya_adapter import MayaAdapter
# from .max_adapter import MaxAdapter
