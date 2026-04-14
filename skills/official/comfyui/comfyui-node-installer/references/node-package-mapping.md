# ComfyUI 节点包映射表

> 常用节点类型到其所属包的映射
> 来源: ComfyUI-Manager, comfyui-arbo-mcp-hub

## 节点包映射

```python
NODE_TYPE_TO_PACKAGE = {
    # ========== 采样器相关 ==========
    "KSampler": None,  # 内置节点
    "KSamplerAdvanced": None,
    "KSamplerSelect": {"name": "comfyui_kampler_select", "url": "https://github.com/..."},
    
    # ========== ControlNet ==========
    "ControlNetApply": None,  # 内置
    "ControlNetApplyAdvanced": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "CannyEdgePreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "OpenposePreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "DepthPreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "LineartPreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "M-LSDPreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "ScribblePreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "SemanticSegmentor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    
    # ========== 动画 ==========
    "AnimateDiffLoader": {"name": "ComfyUI-AnimateDiff-Evolved", "url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved"},
    "ADE_AnimateDiffLoader": {"name": "ComfyUI-AnimateDiff-Evolved", "url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved"},
    "ADE_AnimateDiffLoaderWithContext": {"name": "ComfyUI-AnimateDiff-Evolved", "url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved"},
    "ADE_StandardUniformContextOptions": {"name": "ComfyUI-AnimateDiff-Evolved", "url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved"},
    
    # ========== 视频 ==========
    "VHS_LoadVideo": {"name": "ComfyUI-VideoHelperSuite", "url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "VHS_LoadVideoPath": {"name": "ComfyUI-VideoHelperSuite", "url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "VHS_VideoCombine": {"name": "ComfyUI-VideoHelperSuite", "url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "VHS_BatchManager": {"name": "ComfyUI-VideoHelperSuite", "url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    
    # ========== 工具节点 ==========
    "CR_Image_Panel": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    "CR_Prompt_Text": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    "CR_Seed": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    "CR_PromptMixer": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    "CR_UpscaleImage": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    "CR_ApplyLoRA": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    "CR_ModelMergeStack": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    "CR_LoRAStack": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    
    # ========== rgthree 节点 ==========
    "Reroute": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    "Context": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    "Context Big": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    "Display Any": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    "Fast Muter": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    "Fast Bypasser": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    "Node Comparer": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    "Seed": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    
    # ========== WAS Node Suite ==========
    "WAS_Text_Add_Tokens": {"name": "was-node-suite-comfyui", "url": "https://github.com/WASasquatch/was-node-suite-comfyui"},
    "WAS_Text_Search_and_Replace": {"name": "was-node-suite-comfyui", "url": "https://github.com/WASasquatch/was-node-suite-comfyui"},
    "WAS_Text_Concatenate": {"name": "was-node-suite-comfyui", "url": "https://github.com/WASasquatch/was-node-suite-comfyui"},
    "WAS_Image_Blend": {"name": "was-node-suite-comfyui", "url": "https://github.com/WASasquatch/was-node-suite-comfyui"},
    "WAS_Image_Blur": {"name": "was-node-suite-comfyui", "url": "https://github.com/WASasquatch/was-node-suite-comfyui"},
    "WAS_Image_Save": {"name": "was-node-suite-comfyui", "url": "https://github.com/WASasquatch/was-node-suite-comfyui"},
    
    # ========== pythongosssss 自定义脚本 ==========
    "ShowText|pysssss": {"name": "ComfyUI-Custom-Scripts", "url": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts"},
    "SaveText|pysssss": {"name": "ComfyUI-Custom-Scripts", "url": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts"},
    "CheckpointLoader|pysssss": {"name": "ComfyUI-Custom-Scripts", "url": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts"},
    
    # ========== ComfyUI-Manager 相关 ==========
    "ManagerButton": None,  # Manager 内置
    
    # ========== 图像处理 ==========
    "ImageCompositeMasked": None,  # 内置
    "ImageBlend": {"name": "ComfyUI-Image-Selector", "url": "https://github.com/SLAPaper/ComfyUI-Image-Selector"},
    "ImageSelector": {"name": "ComfyUI-Image-Selector", "url": "https://github.com/SLAPaper/ComfyUI-Image-Selector"},
    
    # ========== 条件/逻辑 ==========
    "CLIPSetLastLayer": None,  # 内置
    "CLIPTextEncodeSDXL": {"name": "comfyui-sd-xl", "url": "https://github.com/comfyanonymous/ComfyUI"},
    "CLIPTextEncodeSDXLRefiner": {"name": "comfyui-sd-xl", "url": "https://github.com/comfyanonymous/ComfyUI"},
    
    # ========== 模型加载器 ==========
    "CheckpointLoaderSimple": None,  # 内置
    "CheckpointLoader": None,  # 内置
    "UNETLoader": None,  # 内置
    "CLIPLoader": None,  # 内置
    "VAELoader": None,  # 内置
    "LoraLoader": None,  # 内置
    "LoraLoaderModelOnly": {"name": "ComfyUI-LoRA-Loader", "url": "https://github.com/..."},
    "ControlNetLoader": None,  # 内置
    "DiffControlNetLoader": None,  # 内置
    "ControlNetLoaderDiffusers": {"name": "ComfyUI-ControlNet-Diffusers", "url": "https://github.com/..."},
    
    # ========== 放大/超分 ==========
    "UpscaleModelLoader": None,  # 内置
    "ImageUpscaleWithModel": None,  # 内置
    "UltimateSDUpscale": {"name": "ComfyUI-UltimateSDUpscale", "url": "https://github.com/ssitu/ComfyUI-UltimateSDUpscale"},
    "UltimateSDUpscaleNoUpscale": {"name": "ComfyUI-UltimateSDUpscale", "url": "https://github.com/ssitu/ComfyUI-UltimateSDUpscale"},
    
    # ========== 修复/重绘 ==========
    "INPAINT_MaskedFill": {"name": "ComfyUI-Inpaint-CropAndStitch", "url": "https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch"},
    "INPAINT_CropAndStitch": {"name": "ComfyUI-Inpaint-CropAndStitch", "url": "https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch"},
    
    # ========== 3D 相关 ==========
    "Zero123": {"name": "ComfyUI-Zero123", "url": "https://github.com/..."},
    "Zero123Conditioning": {"name": "ComfyUI-Zero123", "url": "https://github.com/..."},
    
    # ========== 其他常用 ==========
    "PreviewImage": None,  # 内置
    "SaveImage": None,  # 内置
    "LoadImage": None,  # 内置
    "LoadImageMask": None,  # 内置
    "EmptyImage": None,  # 内置
    "ImageScale": None,  # 内置
    "ImageScaleBy": None,  # 内置
    "ImageScaleToTotalPixels": {"name": "ComfyUI-Image-Selector", "url": "https://github.com/SLAPaper/ComfyUI-Image-Selector"},
    
    # ========== 高级采样 ==========
    "SamplerCustom": {"name": "ComfyUI-Advanced-ControlNet", "url": "https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet"},
    "ACN_AdvancedControlNetApply": {"name": "ComfyUI-Advanced-ControlNet", "url": "https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet"},
    "ACN_ControlNetLoaderWithNoiseSelect": {"name": "ComfyUI-Advanced-ControlNet", "url": "https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet"},
}

# 已知节点迁移映射（旧名称 → 新名称）
NODE_MIGRATION_MAP = {
    "CheckpointLoader": "CheckpointLoaderSimple",
    "CLIPTextEncode": "CLIPTextEncode",  # 相同
    "VAELoader": "VAELoader",  # 相同
    "LoraLoader": "LoraLoader",  # 相同
    "ControlNetLoader": "ControlNetLoader",  # 相同
}
```

## 使用示例

```python
from comfyui_node_installer import NODE_TYPE_TO_PACKAGE, NODE_MIGRATION_MAP

# 查询节点所属包
node_type = "VHS_LoadVideo"
package_info = NODE_TYPE_TO_PACKAGE.get(node_type)

if package_info:
    print(f"节点 {node_type} 需要安装: {package_info['name']}")
    print(f"安装地址: {package_info['url']}")
elif package_info is None:
    print(f"节点 {node_type} 是 ComfyUI 内置节点")
else:
    print(f"节点 {node_type} 未知，可能需要手动查找")
```

## 如何添加新映射

1. 在 GitHub 上找到节点所属的仓库
2. 添加到 `NODE_TYPE_TO_PACKAGE` 字典
3. 如果节点已重命名，添加到 `NODE_MIGRATION_MAP`

---

*映射表版本: 0.1.0*
*最后更新: 2026-04-10*
