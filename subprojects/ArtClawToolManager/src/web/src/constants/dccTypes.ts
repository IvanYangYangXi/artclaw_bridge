// DCC type presets and event constants for ArtClaw Tool Manager
import type { Language } from '../types'

export const DCC_TYPE_PRESETS: Record<string, string[]> = {
  ue5: ['AActor', 'UObject', 'UStaticMesh', 'USkeletalMesh', 'UMaterial', 'UMaterialInstance', 'UTexture2D', 'UBlueprint', 'UWorld', 'UStaticMeshComponent'],
  maya2024: ['mesh', 'nurbsSurface', 'nurbsCurve', 'joint', 'camera', 'light', 'transform', 'locator'],
  max2024: ['Editable_Mesh', 'Editable_Poly', 'Bone', 'Camera', 'Light', 'Spline', 'Helper'],
  blender: ['MESH', 'ARMATURE', 'CURVE', 'SURFACE', 'CAMERA', 'LIGHT', 'EMPTY', 'FONT', 'GPENCIL'],
  comfyui: ['CheckpointLoaderSimple', 'KSampler', 'VAEDecode', 'CLIPTextEncode', 'SaveImage', 'LoadImage', 'ControlNetApply'],
  sp: ['TextureSet', 'FillLayer', 'PaintLayer', 'GroupLayer', 'MaskLayer'],
  sd: ['SDSBSCompGraph', 'SDNode', 'SDResource', 'SDPackage'],
}

export interface DCCEventDef {
  event: string
  label: string
  labelEn: string
  timing: string[]
}

export const DCC_EVENTS: Record<string, DCCEventDef[]> = {
  ue5: [
    { event: 'asset.save.pre',   label: '保存拦截',   labelEn: 'Save Intercept',    timing: ['pre'] },
    { event: 'asset.save',       label: '资源保存',   labelEn: 'Asset Save',         timing: ['post'] },
    { event: 'asset.import.pre', label: '导入拦截',   labelEn: 'Import Intercept',   timing: ['pre'] },
    { event: 'asset.import',     label: '资源导入',   labelEn: 'Asset Import',        timing: ['post'] },
    { event: 'asset.delete.pre', label: '删除拦截',   labelEn: 'Delete Intercept',   timing: ['pre'] },
    { event: 'asset.delete',     label: '资源删除',   labelEn: 'Asset Delete',        timing: ['post'] },
    { event: 'level.load',       label: '关卡加载',   labelEn: 'Level Load',          timing: ['post'] },
    { event: 'editor.startup',   label: '编辑器启动', labelEn: 'Editor Startup',      timing: ['post'] },
  ],
  maya2024: [
    { event: 'file.save', label: '文件保存', labelEn: 'File Save', timing: ['pre', 'post'] },
    { event: 'file.export', label: '文件导出', labelEn: 'File Export', timing: ['pre', 'post'] },
    { event: 'file.import', label: '文件导入', labelEn: 'File Import', timing: ['pre', 'post'] },
    { event: 'file.open', label: '文件打开', labelEn: 'File Open', timing: ['post'] },
    { event: 'scene.new', label: '新建场景', labelEn: 'New Scene', timing: ['post'] },
  ],
  blender: [
    { event: 'file.save', label: '文件保存', labelEn: 'File Save', timing: ['pre', 'post'] },
    { event: 'file.load', label: '文件加载', labelEn: 'File Load', timing: ['post'] },
    { event: 'render.start', label: '开始渲染', labelEn: 'Render Start', timing: ['pre', 'post'] },
  ],
  comfyui: [
    { event: 'workflow.queue', label: '提交工作流', labelEn: 'Queue Workflow', timing: ['pre', 'post'] },
    { event: 'workflow.complete', label: '工作流完成', labelEn: 'Workflow Complete', timing: ['post'] },
  ],
  sp: [
    { event: 'project.save', label: '项目保存', labelEn: 'Project Save', timing: ['pre', 'post'] },
    { event: 'export.textures', label: '导出贴图', labelEn: 'Export Textures', timing: ['pre', 'post'] },
  ],
  sd: [
    { event: 'graph.compute', label: '图表计算', labelEn: 'Graph Compute', timing: ['pre', 'post'] },
    { event: 'package.save', label: '包保存', labelEn: 'Package Save', timing: ['pre', 'post'] },
  ],
}

/** Get localized event label */
export function getEventLabel(dcc: string, event: string, language: Language): string {
  const events = DCC_EVENTS[dcc]
  if (!events) return event
  const found = events.find((e) => e.event === event)
  if (!found) return event
  return language === 'zh' ? found.label : found.labelEn
}

/** Get DCC display name */
export const DCC_DISPLAY_NAMES: Record<string, string> = {
  ue5: 'UE5',
  maya2024: 'Maya',
  max2024: '3ds Max',
  blender: 'Blender',
  comfyui: 'ComfyUI',
  sp: 'Substance Painter',
  sd: 'Substance Designer',
}
