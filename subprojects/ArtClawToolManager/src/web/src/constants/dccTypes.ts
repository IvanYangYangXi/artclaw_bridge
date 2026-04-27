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
  event: string   // full value including timing suffix, e.g. "asset.save.pre", "file.save.post"
  label: string
  labelEn: string
}

export const DCC_EVENTS: Record<string, DCCEventDef[]> = {
  ue5: [
    { event: 'asset.save.pre',    label: '保存拦截 (pre)',     labelEn: 'Save Intercept (pre)'    },
    { event: 'asset.save.post',   label: '资源保存 (post)',    labelEn: 'Asset Save (post)'       },
    { event: 'asset.import.post', label: '资源导入 (post)',    labelEn: 'Asset Import (post)'     },
    { event: 'asset.delete.pre',  label: '删除前检查 (pre)',   labelEn: 'Pre-Delete Check (pre)'  },
    { event: 'asset.delete.post', label: '资源删除 (post)',    labelEn: 'Asset Delete (post)'     },
    { event: 'asset.place.post',  label: '资源放置到场景 (post)', labelEn: 'Asset Placed (post)' },
    { event: 'level.load.post',   label: '关卡加载 (post)',    labelEn: 'Level Load (post)'       },
    { event: 'editor.startup',    label: '编辑器启动',         labelEn: 'Editor Startup'          },
  ],
  maya2024: [
    { event: 'file.save.pre',    label: '文件保存前',   labelEn: 'File Pre-Save'    },
    { event: 'file.save.post',   label: '文件保存后',   labelEn: 'File Post-Save'   },
    { event: 'file.export.pre',  label: '文件导出前',   labelEn: 'File Pre-Export'  },
    { event: 'file.export.post', label: '文件导出后',   labelEn: 'File Post-Export' },
    { event: 'file.import.pre',  label: '文件导入前',   labelEn: 'File Pre-Import'  },
    { event: 'file.import.post', label: '文件导入后',   labelEn: 'File Post-Import' },
    { event: 'file.open.post',   label: '文件打开后',   labelEn: 'File Open'        },
    { event: 'scene.new.post',   label: '新建场景后',   labelEn: 'New Scene'        },
  ],
  blender: [
    { event: 'file.save.post',   label: '文件保存后',   labelEn: 'File Post-Save'   },
    { event: 'file.open.post',   label: '文件打开后',   labelEn: 'File Open'        },
    { event: 'render.pre',       label: '渲染开始前',   labelEn: 'Pre-Render'       },
    { event: 'render.post',      label: '渲染完成后',   labelEn: 'Post-Render'      },
  ],
  comfyui: [
    { event: 'workflow.queue.pre',   label: '提交工作流前',   labelEn: 'Pre-Queue Workflow'    },
    { event: 'workflow.queue.post',  label: '提交工作流后',   labelEn: 'Post-Queue Workflow'   },
    { event: 'workflow.complete',    label: '工作流完成',     labelEn: 'Workflow Complete'     },
  ],
  sp: [
    { event: 'project.save.pre',       label: '项目保存前',   labelEn: 'Project Pre-Save'      },
    { event: 'project.save.post',      label: '项目保存后',   labelEn: 'Project Post-Save'     },
    { event: 'export.textures.pre',    label: '导出贴图前',   labelEn: 'Pre-Export Textures'   },
    { event: 'export.textures.post',   label: '导出贴图后',   labelEn: 'Post-Export Textures'  },
  ],
  sd: [
    { event: 'graph.compute.pre',  label: '图表计算前',   labelEn: 'Pre-Compute Graph'  },
    { event: 'graph.compute.post', label: '图表计算后',   labelEn: 'Post-Compute Graph' },
    { event: 'package.save.pre',   label: '包保存前',     labelEn: 'Package Pre-Save'   },
    { event: 'package.save.post',  label: '包保存后',     labelEn: 'Package Post-Save'  },
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
