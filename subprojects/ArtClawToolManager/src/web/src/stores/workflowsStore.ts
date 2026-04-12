// Ref: docs/specs/architecture-design.md#DataModel
// Workflows state: list, filters, view mode, favorites
import { create } from 'zustand'
import type { WorkflowItem, WorkflowTab, ToolSource, ToolStatus } from '../types'
import { fetchWorkflows, favoriteWorkflow, unfavoriteWorkflow } from '../api/client'

// ---------- Mock Data ----------

const MOCK_WORKFLOWS: WorkflowItem[] = [
  {
    id: 'official/sdxl-portrait',
    name: 'SDXL 肖像摄影',
    description: '使用 SDXL 模型生成高质量肖像照片，支持多种风格和构图',
    type: 'workflow',
    source: 'official',
    targetDCCs: ['comfyui'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: false, favorited: true },
    stats: { downloads: 3200, rating: 4.9, useCount: 85 },
    previewImage: '',
    version: '1.2.0',
    parameters: [
      { id: 'prompt', name: '提示词', type: 'string', required: true, multiline: true, placeholder: '描述你想生成的肖像...' },
      { id: 'negative', name: '反向提示词', type: 'string', required: false, multiline: true, default: 'blurry, low quality, deformed' },
      { id: 'width', name: '宽度', type: 'number', required: false, default: 1024, min: 512, max: 2048, step: 64 },
      { id: 'height', name: '高度', type: 'number', required: false, default: 1024, min: 512, max: 2048, step: 64 },
      { id: 'steps', name: '采样步数', type: 'number', required: false, default: 20, min: 1, max: 50 },
      { id: 'sampler', name: '采样器', type: 'enum', required: false, default: 'euler_ancestral', options: ['euler', 'euler_ancestral', 'dpmpp_2m', 'dpmpp_sde'] },
      { id: 'hires_fix', name: '高清修复', type: 'boolean', required: false, default: false },
    ],
  },
  {
    id: 'official/flux-dev-txt2img',
    name: 'Flux Dev 文生图',
    description: 'Flux Dev 模型标准文生图流程，支持高分辨率输出',
    type: 'workflow',
    source: 'official',
    targetDCCs: ['comfyui'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: true, favorited: false },
    stats: { downloads: 2800, rating: 4.8, useCount: 62 },
    previewImage: '',
    version: '1.0.0',
    parameters: [
      { id: 'prompt', name: '提示词', type: 'string', required: true, multiline: true, placeholder: '输入提示词...' },
      { id: 'width', name: '宽度', type: 'number', required: false, default: 1024, min: 512, max: 2048, step: 64 },
      { id: 'height', name: '高度', type: 'number', required: false, default: 1024, min: 512, max: 2048, step: 64 },
      { id: 'guidance', name: '引导强度', type: 'number', required: false, default: 3.5, min: 1, max: 10, step: 0.5 },
      { id: 'steps', name: '采样步数', type: 'number', required: false, default: 20, min: 1, max: 50 },
    ],
  },
  {
    id: 'marketplace/anime-style',
    name: '二次元风格生成',
    description: '动漫风格角色生成工作流，包含 LoRA 切换和 ControlNet 姿态控制',
    type: 'workflow',
    source: 'marketplace',
    targetDCCs: ['comfyui'],
    status: 'not_installed',
    stats: { downloads: 1500, rating: 4.6, useCount: 0 },
    previewImage: '',
    version: '0.8.0',
  },
  {
    id: 'marketplace/product-photo',
    name: '产品摄影增强',
    description: '电商产品照片增强与背景替换，支持批量处理',
    type: 'workflow',
    source: 'marketplace',
    targetDCCs: ['comfyui'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: false, favorited: false },
    stats: { downloads: 980, rating: 4.5, useCount: 23 },
    previewImage: '',
    version: '1.1.0',
  },
  {
    id: 'user/my-inpaint-flow',
    name: '我的局部重绘流程',
    description: '自定义的局部重绘工作流，针对人像面部优化',
    type: 'workflow',
    source: 'user',
    targetDCCs: ['comfyui'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: false, favorited: false },
    stats: { downloads: 0, rating: 0, useCount: 12 },
    previewImage: '',
    version: '0.1.0',
  },
]

// ---------- Store ----------

interface WorkflowsState {
  workflows: WorkflowItem[]
  loading: boolean
  error: string | null

  // Filters
  activeTab: WorkflowTab
  searchQuery: string
  viewMode: 'grid' | 'list'
  favoritesOnly: boolean // 仅显示已收藏

  // Computed
  filteredWorkflows: () => WorkflowItem[]

  // Actions
  setActiveTab: (tab: WorkflowTab) => void
  setSearchQuery: (q: string) => void
  setViewMode: (mode: 'grid' | 'list') => void
  setFavoritesOnly: (favoritesOnly: boolean) => void
  fetchWorkflowsList: () => Promise<void>
  doFavorite: (id: string) => Promise<void>
  doUnfavorite: (id: string) => Promise<void>
}

const TAB_SOURCE_MAP: Record<WorkflowTab, ToolSource | null> = {
  all: null,
  official: 'official',
  marketplace: 'marketplace',
  mine: 'user',
}

export const useWorkflowsStore = create<WorkflowsState>((set, get) => ({
  workflows: MOCK_WORKFLOWS,
  loading: false,
  error: null,

  activeTab: 'all',
  searchQuery: '',
  viewMode: 'grid',
  favoritesOnly: false,

  filteredWorkflows: () => {
    const { workflows, activeTab, searchQuery, favoritesOnly } = get()
    let list = workflows

    const source = TAB_SOURCE_MAP[activeTab]
    if (source) {
      list = list.filter((w) => w.source === source)
    }

    if (favoritesOnly) {
      list = list.filter((w) => w.runtimeStatus?.favorited === true)
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(
        (w) =>
          w.name.toLowerCase().includes(q) ||
          w.description.toLowerCase().includes(q),
      )
    }

    return list
  },

  setActiveTab: (tab) => set({ activeTab: tab }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setViewMode: (mode) => set({ viewMode: mode }),
  setFavoritesOnly: (v) => set({ favoritesOnly: v }),

  fetchWorkflowsList: async () => {
    set({ loading: true, error: null })
    try {
      const res = await fetchWorkflows()
      if (res.success && Array.isArray(res.data)) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const mapped: WorkflowItem[] = (res.data as any[]).map((raw) => ({
          id: raw.id as string,
          name: raw.name as string,
          description: (raw.description as string) ?? '',
          type: 'workflow' as const,
          source: (raw.source as ToolSource) ?? 'official',
          targetDCCs: (raw.target_dccs as string[]) ?? [],
          status: (raw.status as ToolStatus) ?? 'installed',
          runtimeStatus: {
            enabled: (raw.is_enabled as boolean) ?? true,
            pinned: (raw.is_pinned as boolean) ?? false,
            favorited: (raw.is_favorited as boolean) ?? false,
          },
          stats: {
            downloads: (raw.downloads as number) ?? 0,
            rating: (raw.rating as number) ?? 0,
            useCount: (raw.use_count as number) ?? 0,
          },
          previewImage: (raw.preview_image as string) ?? '',
          version: (raw.version as string) ?? '0.0.0',
        }))
        set({ workflows: mapped })
      }
    } catch {
      // Keep mock data on error
      console.warn('[Workflows] API unavailable, using mock data')
    } finally {
      set({ loading: false })
    }
  },

  // Optimistic updates for favorite
  doFavorite: async (id) => {
    set((s) => ({
      workflows: s.workflows.map((wf) =>
        wf.id === id && wf.runtimeStatus
          ? { ...wf, runtimeStatus: { ...wf.runtimeStatus, favorited: true } }
          : wf.id === id && !wf.runtimeStatus
            ? { ...wf, runtimeStatus: { enabled: true, pinned: false, favorited: true } }
            : wf,
      ),
    }))
    try { await favoriteWorkflow(id) } catch { /* rollback if needed */ }
  },

  doUnfavorite: async (id) => {
    set((s) => ({
      workflows: s.workflows.map((wf) =>
        wf.id === id && wf.runtimeStatus
          ? { ...wf, runtimeStatus: { ...wf.runtimeStatus, favorited: false } }
          : wf,
      ),
    }))
    try { await unfavoriteWorkflow(id) } catch { /* rollback if needed */ }
  },
}))
