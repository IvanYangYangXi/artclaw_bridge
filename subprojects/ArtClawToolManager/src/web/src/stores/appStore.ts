// Ref: docs/specs/architecture-design.md#TechStack
// Global application state
import { create } from 'zustand'
import type { ConnectionStatus, Language, DCCOption, AgentPlatformOption, AgentOption } from '../types'

export type SendMode = 'enter' | 'ctrl-enter'

interface AppState {
  // Connection
  connectionStatus: ConnectionStatus

  // Language / Theme
  language: Language
  sidebarCollapsed: boolean

  // Send mode
  sendMode: SendMode

  // DCC selection
  dccOptions: DCCOption[]
  currentDCC: string

  // Agent platform + agent
  agentPlatforms: AgentPlatformOption[]
  currentPlatform: string
  agents: AgentOption[]
  currentAgent: string

  // Actions
  setConnectionStatus: (status: ConnectionStatus) => void
  setLanguage: (lang: Language) => void
  toggleSidebar: () => void
  setSendMode: (mode: SendMode) => void
  setCurrentDCC: (dcc: string) => void
  setCurrentPlatform: (platform: string) => void
  setCurrentAgent: (agent: string) => void
  fetchDCCOptions: () => Promise<void>
  fetchAgents: () => Promise<void>
}

// Load send mode from localStorage
const savedSendMode = (typeof localStorage !== 'undefined' && localStorage.getItem('artclaw_send_mode')) as SendMode | null

export const useAppStore = create<AppState>((set, get) => ({
  connectionStatus: 'disconnected',

  language: 'zh',
  sidebarCollapsed: false,
  sendMode: savedSendMode || 'enter',

  dccOptions: [
    { id: 'comfyui', name: 'ComfyUI', icon: '🎨', connected: false },
    { id: 'ue57', name: 'UE5', icon: '🎮', connected: false },
    { id: 'maya2024', name: 'Maya', icon: '🗿', connected: false },
    { id: 'max2024', name: '3ds Max', icon: '📐', connected: false },
    { id: 'blender', name: 'Blender', icon: '🧊', connected: false },
    { id: 'houdini', name: 'Houdini', icon: '🌊', connected: false },
    { id: 'sp', name: 'SP', icon: '🖌️', connected: false },
    { id: 'sd', name: 'SD', icon: '🎯', connected: false },
  ],
  currentDCC: 'comfyui',

  agentPlatforms: [
    { id: 'openclaw', name: 'OpenClaw' },
    { id: 'lobsterai', name: 'LobsterAI' },
    { id: 'claude', name: 'Claude' },
  ],
  currentPlatform: 'openclaw',

  agents: [],
  currentAgent: '',

  setConnectionStatus: (status) => set({ connectionStatus: status }),
  setLanguage: (lang) => set({ language: lang }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  setSendMode: (mode) => {
    localStorage.setItem('artclaw_send_mode', mode)
    set({ sendMode: mode })
  },

  setCurrentDCC: (dcc) => set({ currentDCC: dcc }),

  setCurrentPlatform: (platform) => {
    set({ currentPlatform: platform })
    // Auto-select first agent for this platform
    const allAgents = get().agents
    const platformAgents = allAgents.filter((a) => a.platform === platform)
    if (platformAgents.length > 0) {
      set({ currentAgent: platformAgents[0].id })
    } else {
      set({ currentAgent: '' })
    }
  },

  setCurrentAgent: (agent) => set({ currentAgent: agent }),

  fetchDCCOptions: async () => {
    try {
      const res = await fetch('/api/v1/system/dcc-options')
      const json = await res.json()
      if (json.success && Array.isArray(json.data)) {
        set({
          dccOptions: json.data.map((d: Record<string, unknown>) => ({
            id: d.id as string,
            name: d.name as string,
            icon: d.icon as string,
            connected: d.connected as boolean,
          })),
        })
      }
    } catch {
      // Keep defaults
    }
  },

  fetchAgents: async () => {
    try {
      const res = await fetch('/api/v1/system/agents')
      const json = await res.json()
      if (json.success && json.data?.platforms) {
        const platforms: AgentPlatformOption[] = []
        const allAgents: AgentOption[] = []
        for (const p of json.data.platforms as Array<{ id: string; name: string; agents: Array<{ id: string; name: string }> }>) {
          platforms.push({ id: p.id, name: p.name })
          for (const a of p.agents) {
            allAgents.push({ id: a.id, name: a.name, platform: p.id })
          }
        }
        // Select first agent of current platform
        const currentPlatform = get().currentPlatform
        const firstAgent = allAgents.find((a) => a.platform === currentPlatform)
        set({
          agentPlatforms: platforms,
          agents: allAgents,
          currentAgent: firstAgent?.id ?? '',
        })
      }
    } catch {
      // Keep defaults
    }
  },
}))
