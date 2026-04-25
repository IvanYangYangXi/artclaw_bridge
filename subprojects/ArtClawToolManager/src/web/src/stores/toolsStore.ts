// Ref: docs/specs/architecture-design.md#DataModel
// Tools state: list, filters, selection, batch operations
import { create } from 'zustand'
import type { ToolItemExtended, ToolTab, ToolSource, ToolItemStatus, ImplementationType } from '../types'
import {
  fetchTools,
  createTool,
  deleteTool,
  pinTool,
  unpinTool,
  favoriteTool,
  unfavoriteTool,
  batchToolOperation,
} from '../api/client'

// ---------- Mock Data ----------

const MOCK_TOOLS: ToolItemExtended[] = [
  {
    id: 'official/node-installer',
    name: '节点安装器',
    description: '自动检测并安装缺失的 ComfyUI 自定义节点',
    type: 'tool',
    source: 'official',
    targetDCCs: ['comfyui'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: true, favorited: false },
    stats: { downloads: 5200, rating: 4.9, useCount: 89 },
    version: '1.2.0',
    implementationType: 'script',
    triggerCount: 1,
  },
  {
    id: 'official/batch-rename',
    name: '批量重命名',
    description: '批量重命名选中的场景对象，支持前缀、后缀、编号等规则',
    type: 'tool',
    source: 'official',
    targetDCCs: ['ue5', 'maya2024', 'blender'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: false, favorited: true },
    stats: { downloads: 3800, rating: 4.7, useCount: 56 },
    version: '2.0.0',
    implementationType: 'script',
    triggerCount: 0,
    manifest: {
      name: '批量重命名',
      inputs: [
        { id: 'prefix', name: '前缀', type: 'string', required: true, default: 'SM_' },
        { id: 'suffix', name: '后缀', type: 'string', required: false, default: '' },
        { id: 'use_numbering', name: '使用编号', type: 'boolean', required: false, default: true },
        { id: 'start_number', name: '起始编号', type: 'number', required: false, default: 1, min: 0, max: 9999 },
        { id: 'padding', name: '编号位数', type: 'number', required: false, default: 3, min: 1, max: 6 },
      ],
    },
  },
  {
    id: 'marketplace/auto-lod',
    name: '自动 LOD 生成',
    description: '自动为模型生成多级 LOD，优化渲染性能',
    type: 'tool',
    source: 'marketplace',
    targetDCCs: ['ue5'],
    status: 'not_installed',
    stats: { downloads: 1200, rating: 4.5, useCount: 0 },
    version: '1.0.0',
    implementationType: 'script',
  },
  {
    id: 'marketplace/texture-optimizer',
    name: '贴图优化器',
    description: '批量压缩和优化贴图资源，降低内存占用',
    type: 'tool',
    source: 'marketplace',
    targetDCCs: ['ue5', 'maya2024'],
    status: 'update_available',
    runtimeStatus: { enabled: true, pinned: false, favorited: false },
    stats: { downloads: 2100, rating: 4.6, useCount: 23 },
    version: '1.3.0',
    implementationType: 'composite',
    triggerCount: 2,
  },
  {
    id: 'user/quick-txt2img',
    name: '快速文生图',
    description: '包装 comfyui-txt2img Skill 的快捷工具，固定尺寸 1024x1024',
    type: 'tool',
    source: 'user',
    targetDCCs: ['comfyui'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: false, favorited: false },
    stats: { downloads: 0, rating: 0, useCount: 15 },
    version: '1.0.0',
    implementationType: 'skill_wrapper',
    triggerCount: 0,
    presets: [
      {
        id: 'portrait',
        name: '肖像写真',
        description: '适合人像摄影的预设',
        isDefault: true,
        values: {
          prompt: 'portrait, professional lighting, high quality',
          negative_prompt: 'blurry, low quality',
          steps: 20,
          cfg_scale: 7.5
        },
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z'
      },
      {
        id: 'landscape',
        name: '风景摄影',
        description: '适合风景照片的预设',
        isDefault: false,
        values: {
          prompt: 'landscape, natural lighting, detailed',
          negative_prompt: 'people, buildings',
          steps: 25,
          cfg_scale: 8.0
        },
        createdAt: '2024-01-02T00:00:00Z',
        updatedAt: '2024-01-02T00:00:00Z'
      },
      {
        id: 'anime',
        name: '动漫风格',
        description: '动漫风格预设',
        isDefault: false,
        values: {
          prompt: 'anime style, vibrant colors, detailed',
          negative_prompt: 'realistic, photo',
          steps: 30,
          cfg_scale: 9.0
        },
        createdAt: '2024-01-03T00:00:00Z',
        updatedAt: '2024-01-03T00:00:00Z'
      }
    ]
  },
  {
    id: 'user/batch-export-fbx',
    name: '批量导出 FBX',
    description: '一键导出选中模型为 FBX，支持动画和前缀配置',
    type: 'tool',
    source: 'user',
    targetDCCs: ['maya2024'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: true, favorited: false },
    stats: { downloads: 0, rating: 0, useCount: 42 },
    version: '1.1.0',
    implementationType: 'script',
    triggerCount: 3,
  },
  {
    id: 'user/naming-check-export',
    name: '命名检查+导出',
    description: '先运行命名检查，通过后自动导出 FBX 的组合工具',
    type: 'tool',
    source: 'user',
    targetDCCs: ['maya2024'],
    status: 'installed', // Tool 不支持 disabled，改为 installed
    runtimeStatus: { enabled: false, pinned: false, favorited: false },
    stats: { downloads: 0, rating: 0, useCount: 5 },
    version: '0.1.0',
    implementationType: 'composite',
    triggerCount: 1,
  },
]

// ---------- Store ----------

interface ToolsState {
  tools: ToolItemExtended[]
  loading: boolean
  error: string | null

  // Filters
  activeTab: ToolTab
  searchQuery: string
  dccFilter: string      // '' = all, or 'ue5', 'maya2024', etc.
  favoritesOnly: boolean // 仅显示已收藏

  // Selection
  selectedToolIds: Set<string>

  // Computed
  filteredTools: () => ToolItemExtended[]

  // Actions
  setActiveTab: (tab: ToolTab) => void
  setSearchQuery: (q: string) => void
  setDCCFilter: (dcc: string) => void
  setFavoritesOnly: (favoritesOnly: boolean) => void
  toggleSelectTool: (id: string) => void
  selectAll: () => void
  clearSelection: () => void
  fetchToolsList: () => Promise<void>
  doCreate: (data: { name: string; description?: string; version?: string; source?: string; target_dccs?: string[]; implementation_type?: string; manifest?: Record<string, unknown> }) => Promise<void>
  doDelete: (id: string) => Promise<void>
  doPin: (id: string) => Promise<void>
  doUnpin: (id: string) => Promise<void>
  doFavorite: (id: string) => Promise<void>
  doUnfavorite: (id: string) => Promise<void>
  batchOperation: (operation: string) => Promise<void>
}

const TAB_SOURCE_MAP: Record<ToolTab, ToolSource | null> = {
  all: null,
  official: 'official',
  marketplace: 'marketplace',
  mine: 'user',
  create: null,
}

export const useToolsStore = create<ToolsState>((set, get) => ({
  tools: MOCK_TOOLS,
  loading: false,
  error: null,

  activeTab: 'all',
  searchQuery: '',
  dccFilter: '',
  favoritesOnly: false,

  selectedToolIds: new Set<string>(),

  filteredTools: () => {
    const { tools, activeTab, searchQuery, dccFilter, favoritesOnly } = get()

    // 'create' tab doesn't filter tools
    if (activeTab === 'create') return []

    let list = tools

    const source = TAB_SOURCE_MAP[activeTab]
    if (source) {
      list = list.filter((t) => t.source === source)
    }

    if (dccFilter) {
      list = list.filter((t) => t.targetDCCs.includes(dccFilter))
    }

    if (favoritesOnly) {
      list = list.filter((t) => t.runtimeStatus?.favorited === true)
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q),
      )
    }

    return list
  },

  setActiveTab: (tab) => set({ activeTab: tab, selectedToolIds: new Set() }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setDCCFilter: (dcc) => set({ dccFilter: dcc }),
  setFavoritesOnly: (favoritesOnly) => set({ favoritesOnly }),

  toggleSelectTool: (id) =>
    set((s) => {
      const next = new Set(s.selectedToolIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { selectedToolIds: next }
    }),

  selectAll: () => {
    const ids = get().filteredTools().map((t) => t.id)
    set({ selectedToolIds: new Set(ids) })
  },

  clearSelection: () => set({ selectedToolIds: new Set() }),

  fetchToolsList: async () => {
    set({ loading: true, error: null })
    try {
      const res = await fetchTools()
      if (res.success && Array.isArray(res.data)) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const mapped: ToolItemExtended[] = (res.data as any[]).map((raw) => ({
          id: raw.id as string,
          name: raw.name as string,
          description: (raw.description as string) ?? '',
          type: 'tool' as const,
          source: (raw.source as ToolSource) ?? 'user',
          targetDCCs: (raw.target_dccs as string[]) ?? [],
          status: (raw.status as ToolItemStatus) ?? 'installed',
          runtimeStatus: {
            enabled: (raw.is_enabled as boolean) ?? true,
            pinned: (raw.is_pinned as boolean) ?? false,
            favorited: (raw.is_favorited as boolean) ?? false,
          },
          stats: { downloads: 0, rating: 0, useCount: (raw.use_count as number) ?? 0 },
          version: (raw.version as string) ?? '0.0.0',
          author: (raw.author as string) ?? '',
          createdAt: (raw.created_at as string) ?? '',
          updatedAt: (raw.updated_at as string) ?? '',
          implementationType: (raw.implementation_type as ImplementationType) ?? 'script',
          manifest: raw.manifest ?? {},
          toolPath: (raw.tool_path as string) ?? '',
        }))
        set({ tools: mapped })
      }
    } catch {
      console.warn('[Tools] API unavailable, using mock data')
    } finally {
      set({ loading: false })
    }
  },

  doCreate: async (data) => {
    try {
      await createTool(data)
      await get().fetchToolsList()
    } catch {
      console.error('[Tools] Create failed')
    }
  },

  doDelete: async (id) => {
    set((s) => ({
      tools: s.tools.filter((t) => t.id !== id),
    }))
    try { await deleteTool(id) } catch { /* rollback if needed */ }
  },

  doPin: async (id) => {
    set((s) => ({
      tools: s.tools.map((t) =>
        t.id === id && t.runtimeStatus
          ? { ...t, runtimeStatus: { ...t.runtimeStatus, pinned: true } }
          : t,
      ),
    }))
    try { await pinTool(id) } catch { /* rollback if needed */ }
  },

  doUnpin: async (id) => {
    set((s) => ({
      tools: s.tools.map((t) =>
        t.id === id && t.runtimeStatus
          ? { ...t, runtimeStatus: { ...t.runtimeStatus, pinned: false } }
          : t,
      ),
    }))
    try { await unpinTool(id) } catch { /* rollback if needed */ }
  },

  doFavorite: async (id) => {
    set((s) => ({
      tools: s.tools.map((t) =>
        t.id === id && t.runtimeStatus
          ? { ...t, runtimeStatus: { ...t.runtimeStatus, favorited: true } }
          : t,
      ),
    }))
    try { await favoriteTool(id) } catch { /* rollback if needed */ }
  },

  doUnfavorite: async (id) => {
    set((s) => ({
      tools: s.tools.map((t) =>
        t.id === id && t.runtimeStatus
          ? { ...t, runtimeStatus: { ...t.runtimeStatus, favorited: false } }
          : t,
      ),
    }))
    try { await unfavoriteTool(id) } catch { /* rollback if needed */ }
  },

  batchOperation: async (operation) => {
    const ids = Array.from(get().selectedToolIds)
    if (ids.length === 0) return

    // Optimistic: apply locally
    if (operation === 'delete') {
      set((s) => ({
        tools: s.tools.filter((t) => !s.selectedToolIds.has(t.id)),
        selectedToolIds: new Set(),
      }))
    } else {
      set({ selectedToolIds: new Set() })
    }

    try { await batchToolOperation(operation, ids) } catch { /* rollback if needed */ }
  },
}))
