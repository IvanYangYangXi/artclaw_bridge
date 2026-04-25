// Ref: docs/specs/architecture-design.md#DataModel
// Skills state: list, filters, selection, batch operations
import { create } from 'zustand'
import type { SkillItem, SkillTab, ToolSource, ToolStatus, SyncStatus } from '../types'
import { fetchSkills, installSkill, uninstallSkill, enableSkill, disableSkill, pinSkill, unpinSkill, updateSkill } from '../api/client'

// ---------- Mock Data ----------

const MOCK_SKILLS: SkillItem[] = [
  {
    id: 'official/comfyui-txt2img',
    name: 'comfyui-txt2img',
    description: 'ComfyUI 文生图标准流程。checkpoint + CLIP + KSampler + VAEDecode + SaveImage',
    type: 'skill',
    source: 'official',
    targetDCCs: ['comfyui'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: true, favorited: false },
    stats: { downloads: 1200, rating: 4.8, useCount: 45 },
    version: '0.1.0',
    priority: 100,
  },
  {
    id: 'official/comfyui-img2img',
    name: 'comfyui-img2img',
    description: 'ComfyUI 图生图工作流构建与执行',
    type: 'skill',
    source: 'official',
    targetDCCs: ['comfyui'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: true, favorited: true },
    stats: { downloads: 980, rating: 4.7, useCount: 32 },
    version: '0.1.0',
  },
  {
    id: 'official/ue5-operation-rules',
    name: 'ue5-operation-rules',
    description: 'UE Editor 操作通用规则和最佳实践',
    type: 'skill',
    source: 'official',
    targetDCCs: ['ue5'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: false, favorited: false },
    stats: { downloads: 2300, rating: 4.9, useCount: 120 },
    version: '1.0.0',
  },
  {
    id: 'official/blender-material-ops',
    name: 'blender-material-ops',
    description: 'Blender 材质创建与节点操作指南',
    type: 'skill',
    source: 'official',
    targetDCCs: ['blender'],
    status: 'not_installed',
    stats: { downloads: 560, rating: 4.5, useCount: 0 },
    version: '0.2.0',
  },
  {
    id: 'marketplace/maya-batch-export',
    name: 'maya-batch-export',
    description: '批量导出 Maya 场景中的模型为 FBX',
    type: 'skill',
    source: 'marketplace',
    targetDCCs: ['maya2024'],
    status: 'not_installed',
    stats: { downloads: 340, rating: 4.3, useCount: 0 },
    version: '1.1.0',
  },
  {
    id: 'marketplace/comfyui-controlnet',
    name: 'comfyui-controlnet',
    description: 'ComfyUI ControlNet 工作流：Canny、OpenPose、Depth 等控制生成',
    type: 'skill',
    source: 'marketplace',
    targetDCCs: ['comfyui'],
    status: 'update_available',
    runtimeStatus: { enabled: true, pinned: false, favorited: false },
    stats: { downloads: 870, rating: 4.6, useCount: 18 },
    version: '0.3.0',
  },
  {
    id: 'official/comfyui-inpainting',
    name: 'comfyui-inpainting',
    description: 'ComfyUI 局部重绘（Inpainting）：修改图像的特定区域',
    type: 'skill',
    source: 'official',
    targetDCCs: ['comfyui'],
    status: 'disabled',
    runtimeStatus: { enabled: false, pinned: false, favorited: false },
    stats: { downloads: 650, rating: 4.4, useCount: 8 },
    version: '0.1.0',
  },
  {
    id: 'user/my-custom-tool',
    name: 'my-custom-tool',
    description: '我的自定义 UE 场景工具',
    type: 'skill',
    source: 'user',
    targetDCCs: ['ue5'],
    status: 'installed',
    runtimeStatus: { enabled: true, pinned: false, favorited: false },
    stats: { downloads: 0, rating: 0, useCount: 5 },
    version: '0.0.1',
  },
]

// ---------- Store ----------

interface SkillsState {
  skills: SkillItem[]
  loading: boolean
  error: string | null

  // Filters
  activeTab: SkillTab
  searchQuery: string
  dccFilter: string      // '' = all, or 'ue5', 'maya2024', etc.
  statusFilter: string   // '' = all, or 'installed', 'not_installed', etc.
  favoritesOnly: boolean // 仅显示已收藏

  // Selection
  selectedSkillIds: Set<string>

  // Computed
  filteredSkills: () => SkillItem[]

  // Actions
  setActiveTab: (tab: SkillTab) => void
  setSearchQuery: (q: string) => void
  setDCCFilter: (dcc: string) => void
  setStatusFilter: (status: string) => void
  setFavoritesOnly: (favoritesOnly: boolean) => void
  toggleSelectSkill: (id: string) => void
  selectAll: () => void
  clearSelection: () => void
  fetchSkillsList: () => Promise<void>
  doInstall: (id: string) => Promise<void>
  doUninstall: (id: string) => Promise<void>
  doUpdate: (id: string) => Promise<void>
  doEnable: (id: string) => Promise<void>
  doDisable: (id: string) => Promise<void>
  doPin: (id: string) => Promise<void>
  doUnpin: (id: string) => Promise<void>
  doSyncFromSource: (id: string) => Promise<void>
  doPublishToSource: (id: string, options?: { version?: string; description?: string; target?: string; dcc?: string }) => Promise<void>
}

const TAB_SOURCE_MAP: Record<SkillTab, ToolSource | null> = {
  all: null,
  official: 'official',
  marketplace: 'marketplace',
  platform: null, // 平台/用户：不是 official、也不是 marketplace 的所有 Skill，见 filteredSkills
}

export const useSkillsStore = create<SkillsState>((set, get) => ({
  skills: MOCK_SKILLS,
  loading: false,
  error: null,

  activeTab: 'all',
  searchQuery: '',
  dccFilter: '',
  statusFilter: '',
  favoritesOnly: false,

  selectedSkillIds: new Set<string>(),

  filteredSkills: () => {
    const { skills, activeTab, searchQuery, dccFilter, statusFilter, favoritesOnly } = get()
    let list = skills

    const source = TAB_SOURCE_MAP[activeTab]
    if (source) {
      list = list.filter((s) => s.source === source)
    }

    // 平台/用户：排除 official 和 marketplace，剩下都归平台
    if (activeTab === 'platform') {
      list = list.filter((s) => s.source !== 'official' && s.source !== 'marketplace')
    }

    if (dccFilter) {
      list = list.filter((s) => s.targetDCCs.includes(dccFilter))
    }

    if (statusFilter === 'pending_publish') {
      list = list.filter((s) => s.syncStatus === 'installed_newer' || s.syncStatus === 'modified' || s.syncStatus === 'no_source')
    } else if (statusFilter === 'no_source') {
      list = list.filter((s) => s.syncStatus === 'no_source')
    } else if (statusFilter) {
      list = list.filter((s) => s.status === statusFilter)
    }

    if (favoritesOnly) {
      list = list.filter((s) => s.runtimeStatus?.favorited === true)
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q),
      )
    }

    return list
  },

  setActiveTab: (tab) => set({ activeTab: tab, selectedSkillIds: new Set() }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setDCCFilter: (dcc) => set({ dccFilter: dcc }),
  setStatusFilter: (status) => set({ statusFilter: status }),
  setFavoritesOnly: (favoritesOnly) => set({ favoritesOnly }),

  toggleSelectSkill: (id) =>
    set((s) => {
      const next = new Set(s.selectedSkillIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { selectedSkillIds: next }
    }),

  selectAll: () => {
    const ids = get().filteredSkills().map((s) => s.id)
    set({ selectedSkillIds: new Set(ids) })
  },

  clearSelection: () => set({ selectedSkillIds: new Set() }),

  fetchSkillsList: async () => {
    set({ loading: true, error: null })
    try {
      const res = await fetchSkills()
      if (res.success && Array.isArray(res.data)) {
        // Map backend flat response to frontend SkillItem shape
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const mapped: SkillItem[] = (res.data as any[]).map((raw) => ({
          id: raw.id as string,
          name: raw.name as string,
          description: (raw.description as string) ?? '',
          type: 'skill' as const,
          source: (raw.source as ToolSource) ?? 'official',
          targetDCCs: (raw.target_dccs as string[]) ?? [],
          status: (raw.status as ToolStatus) ?? 'installed',
          runtimeStatus: {
            enabled: (raw.is_enabled as boolean) ?? true,
            pinned: (raw.is_pinned as boolean) ?? false,
            favorited: (raw.is_favorited as boolean) ?? false,
          },
          stats: { downloads: 0, rating: 0, useCount: (raw.use_count as number) ?? 0 },
          version: (raw.version as string) ?? '0.0.0',
          author: (raw.author as string) ?? '',
          updatedAt: (raw.updated_at as string) ?? '',
          priority: (raw.priority as number) ?? 0,
          sourcePath: (raw.source_path as string) ?? '',
          syncStatus: (raw.sync_status as SyncStatus) ?? 'no_source',
        }))
        set({ skills: mapped })
      }
    } catch {
      // Keep mock data on error
      console.warn('[Skills] API unavailable, using mock data')
    } finally {
      set({ loading: false })
    }
  },

  // Optimistic updates for skill operations
  doInstall: async (id) => {
    set((s) => ({
      skills: s.skills.map((sk) =>
        sk.id === id ? { ...sk, status: 'installed' as ToolStatus, runtimeStatus: { enabled: true, pinned: false, favorited: false } } : sk,
      ),
    }))
    try {
      await installSkill(id)
      // Re-fetch to get correct skill_path and sync_status
      await get().fetchSkillsList()
    } catch { /* rollback if needed */ }
  },

  doUninstall: async (id) => {
    set((s) => ({
      skills: s.skills.map((sk) =>
        sk.id === id ? { ...sk, status: 'not_installed' as ToolStatus, runtimeStatus: undefined } : sk,
      ),
    }))
    try {
      await uninstallSkill(id)
      // Re-fetch to get updated state
      await get().fetchSkillsList()
    } catch { /* rollback if needed */ }
  },

  doUpdate: async (id) => {
    set((s) => ({
      skills: s.skills.map((sk) =>
        sk.id === id ? { ...sk, status: 'installed' as ToolStatus } : sk,
      ),
    }))
    try { await updateSkill(id) } catch { /* rollback if needed */ }
  },

  doEnable: async (id) => {
    set((s) => ({
      skills: s.skills.map((sk) =>
        sk.id === id
          ? { ...sk, status: 'installed' as ToolStatus, runtimeStatus: { ...sk.runtimeStatus!, enabled: true } }
          : sk,
      ),
    }))
    try { await enableSkill(id) } catch { /* rollback if needed */ }
  },

  doDisable: async (id) => {
    set((s) => ({
      skills: s.skills.map((sk) =>
        sk.id === id
          ? { ...sk, status: 'disabled' as ToolStatus, runtimeStatus: { ...sk.runtimeStatus!, enabled: false } }
          : sk,
      ),
    }))
    try { await disableSkill(id) } catch { /* rollback if needed */ }
  },

  doPin: async (id) => {
    set((s) => ({
      skills: s.skills.map((sk) =>
        sk.id === id && sk.runtimeStatus
          ? { ...sk, runtimeStatus: { ...sk.runtimeStatus, pinned: true } }
          : sk,
      ),
    }))
    try { await pinSkill(id) } catch { /* rollback if needed */ }
  },

  doUnpin: async (id) => {
    set((s) => ({
      skills: s.skills.map((sk) =>
        sk.id === id && sk.runtimeStatus
          ? { ...sk, runtimeStatus: { ...sk.runtimeStatus, pinned: false } }
          : sk,
      ),
    }))
    try { await unpinSkill(id) } catch { /* rollback if needed */ }
  },

  doSyncFromSource: async (id) => {
    try {
      await fetch(`/api/v1/skills/${encodeURIComponent(id)}/sync-from-source`, { method: 'POST' })
      // Re-fetch to get updated sync status
      await get().fetchSkillsList()
    } catch (error) {
      console.error('[Skills] Sync from source failed:', error)
    }
  },

  doPublishToSource: async (id, options) => {
    try {
      await fetch(`/api/v1/skills/${encodeURIComponent(id)}/publish-to-source`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version: options?.version,
          description: options?.description,
          target: options?.target,
          dcc: options?.dcc,
        }),
      })
      // Re-fetch to get updated sync status
      await get().fetchSkillsList()
    } catch (error) {
      console.error('[Skills] Publish to source failed:', error)
    }
  },
}))
