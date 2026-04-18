// Ref: docs/specs/architecture-design.md#DataModel
// TypeScript type definitions for ArtClaw Tool Manager

// ---------- Connection & System ----------

export type ConnectionStatus = 'connected' | 'disconnected' | 'connecting'
export type Language = 'zh' | 'en'
export type Theme = 'dark'

export interface SystemStatus {
  version: string
  status: 'running' | 'stopped'
  connectedDCCs: string[]
  stats: {
    totalSkills: number
    installedSkills: number
    totalWorkflows: number
    userTools: number
  }
}

// ---------- DCC & Agent ----------

export interface DCCOption {
  id: string
  name: string
  icon: string
  connected: boolean
}

export interface AgentPlatformOption {
  id: string
  name: string
  configured?: boolean
}

export interface AgentOption {
  id: string
  name: string
  platform: string
}

// ---------- Chat ----------

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  result?: string
  error?: string
  status: 'pending' | 'running' | 'completed' | 'error'
}

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: string
  toolCalls?: ToolCall[]
  images?: string[]
  isStreaming?: boolean
}

export interface ChatSession {
  id: string
  name: string
  createdAt: string
  updatedAt: string
  messageCount: number
}

export interface ContextUsage {
  used: number
  total: number
  percentage: number
}

// ---------- Sync Status ----------

export type SyncStatus = 'synced' | 'source_newer' | 'installed_newer' | 'modified' | 'conflict' | 'no_source' | 'not_installed'

// ---------- Skill / Workflow / Tool ----------

export type ToolItemType = 'skill' | 'workflow' | 'tool'
export type ToolSource = 'official' | 'marketplace' | 'user'
export type ToolStatus = 'not_installed' | 'installed' | 'update_available' | 'disabled'
export type ToolItemStatus = 'not_installed' | 'installed' | 'update_available' // Tool 不支持 disabled

export interface ToolItemStats {
  downloads: number
  rating: number
  useCount: number
}

export interface RuntimeStatus {
  enabled: boolean
  pinned: boolean
  favorited: boolean
}

export interface SkillItem {
  id: string
  name: string
  description: string
  type: 'skill'
  source: ToolSource
  targetDCCs: string[]
  status: ToolStatus
  runtimeStatus?: RuntimeStatus
  paths?: { installed: string; source?: string }
  stats: ToolItemStats
  version: string
  author?: string
  updatedAt?: string
  priority?: number
  sourcePath?: string
  syncStatus?: SyncStatus
}

export interface WorkflowItem {
  id: string
  name: string
  description: string
  type: 'workflow'
  source: ToolSource
  targetDCCs: string[]
  status: ToolStatus
  runtimeStatus?: RuntimeStatus
  paths?: { installed: string; source?: string }
  stats: ToolItemStats
  previewImage?: string
  version?: string
  parameters?: WorkflowParameter[]
}

export interface ToolItem {
  id: string
  name: string
  description: string
  type: 'tool'
  source: ToolSource
  targetDCCs: string[]
  status: ToolItemStatus // Tool 不支持 disabled
  runtimeStatus?: RuntimeStatus
  paths?: { installed: string; source?: string }
  stats: ToolItemStats
  version?: string
  author?: string
  createdAt?: string
  updatedAt?: string
  lastUsed?: string
}

// ---------- Tabs ----------

export type SkillTab = 'all' | 'official' | 'marketplace' | 'platform'
export type WorkflowTab = 'all' | 'official' | 'marketplace' | 'mine'
export type ToolTab = 'all' | 'official' | 'marketplace' | 'mine' | 'create'

// ---------- Slash Commands ----------

export interface SlashCommand {
  command: string
  description: string
  isLocal: boolean
}

// ---------- API Response ----------

export interface ApiResponse<T> {
  success: boolean
  data: T
  meta?: {
    page: number
    limit: number
    total: number
  }
}

export interface ApiError {
  success: false
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

// ---------- Navigation ----------

export type PageKey = 'chat' | 'skills' | 'workflows' | 'tools' | 'settings'

export interface NavItem {
  key: PageKey
  label: string
  icon: string
  path: string
}

// ---------- Workflow Extended ----------

export interface WorkflowParameter {
  id: string
  name: string
  type: 'string' | 'number' | 'boolean' | 'enum' | 'select' | 'image'
  required: boolean
  default?: unknown
  description?: string
  min?: number
  max?: number
  step?: number
  options?: string[]
  multiline?: boolean
  placeholder?: string
}

export interface WorkflowDetail extends WorkflowItem {
  parameters: WorkflowParameter[]
  workflowJson?: Record<string, unknown>
}

// ---------- Execution Context ----------

export interface ExecutionContext {
  type: 'workflow' | 'tool'
  id: string
  name: string
  parameters: WorkflowParameter[]
  values: Record<string, unknown>
  presetId?: string
  needsAI?: boolean
  // Tool execution context: paths and AI guidance
  toolPath?: string           // Tool directory on disk (e.g. ~/.artclaw/tools/user/my-tool/)
  entryScript?: string        // Entry script filename (e.g. main.py)
  aiPrompt?: string           // AI guidance prompt from manifest
  skillRef?: string           // Referenced skill name (for skill_wrapper type)
  implementationType?: string // script | skill_wrapper | composite
}

// ---------- DCC Status (Phase 5) ----------

export interface DCCStatusInfo {
  dcc_type: string
  connected: boolean
  host: string
  port: number
  last_check: number
  last_connected: number
  error: string | null
}

// ---------- Trigger Engine (Phase 5) ----------

export interface TriggerEngineStats {
  running: boolean
  total_rules: number
  scheduled_jobs: number
  event_rules: number
}

export interface DCCEvent {
  dcc_type: string
  event_type: string
  timing: string
  data: Record<string, unknown>
}

// ---------- Tool Extended Types ----------

export type ImplementationType = 'skill_wrapper' | 'script' | 'composite'

export interface ToolManifest {
  id?: string
  name: string
  description?: string
  version?: string
  targetDCCs?: string[]
  defaultFilters?: FilterConfig   // Tool-level default filter conditions
  implementation?: {
    type: ImplementationType
    entry?: string
    function?: string
    skill?: string
    aiPrompt?: string
    fixedParams?: Record<string, unknown>
    tools?: string[]
  }
  inputs?: ToolParameter[]
  outputs?: ToolOutput[]
  triggers?: TriggerRuleData[]
  presets?: ParameterPreset[]
  conditions?: ConditionFilter
}

export interface ToolParameter {
  id: string
  name: string
  type: 'string' | 'number' | 'boolean' | 'enum' | 'file' | 'folder'
  required: boolean
  default?: unknown
  min?: number
  max?: number
  step?: number
  options?: string[]
  description?: string
}

export interface ToolOutput {
  id: string
  name: string
  type: 'string' | 'number' | 'boolean' | 'image' | 'file'
}

export interface ParameterPreset {
  id: string
  name: string
  description?: string
  isDefault?: boolean
  values: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

// ---------- Condition Filter ----------

export interface ConditionFilter {
  pathGlob?: string
  nameRegex?: string
  assetTypes?: string[]
}

// ---------- Tool Extended Item ----------

export interface ToolItemExtended extends ToolItem {
  implementationType?: ImplementationType
  manifest?: ToolManifest
  toolPath?: string
  triggerCount?: number
  presets?: ParameterPreset[]
}

// ---------- Trigger Rules ----------

export type TriggerType = 'manual' | 'event' | 'schedule' | 'watch'
export type EventTiming = 'pre' | 'post'
export type ExecutionMode = 'silent' | 'notify' | 'interactive'

export interface TriggerRuleData {
  id: string
  toolId: string
  name: string
  triggerType: TriggerType
  eventType: string
  eventTiming: EventTiming
  executionMode: ExecutionMode
  conditions: FilterConfig
  parameterPreset: Record<string, unknown>
  isEnabled: boolean
  useDefaultFilters?: boolean
  use_default_filters?: boolean
  scheduleConfig: Record<string, unknown>
  createdAt?: string
  updatedAt?: string
}

export interface TriggerCreateData {
  name: string
  trigger_type: TriggerType
  dcc?: string
  event_type?: string
  event_timing?: EventTiming
  execution_mode?: ExecutionMode
  conditions?: FilterConfig
  parameter_preset?: Record<string, unknown>
  is_enabled?: boolean
  schedule_config?: Record<string, unknown>
}

// ---------- Filter Config (Phase 6) ----------

export interface FileFilterRule {
  pattern: string
  isRegex?: boolean
}

export interface SceneFilterRule {
  pattern: string
  isRegex?: boolean
}

export interface TypeFilter {
  types: string[]
  dcc?: string
  isRegex?: boolean
}

export interface FilterConfig {
  fileRules?: FileFilterRule[]
  sceneRules?: SceneFilterRule[]
  typeFilter?: TypeFilter
  selectionOnly?: boolean
  path?: Array<{ pattern: string; exclude?: boolean }>
  name?: Array<{ pattern: string; exclude?: boolean }>
}

export interface FilterPreset {
  id: string
  name: string
  description?: string
  dcc?: string[]
  filter: FilterConfig
  createdAt?: string
  updatedAt?: string
}

// ---------- Session Entry (Phase 6) ----------

export interface SessionEntry {
  id: string
  label: string
  sessionKey: string
  cachedMessages: ChatMessage[]
  createdAt: string
  isActive: boolean
}

// ---------- Alert System ----------

export type AlertLevel = 'warning' | 'error'

export interface Alert {
  id: string
  level: AlertLevel
  source: string
  title: string
  detail: string
  createdAt: string
  resolvedAt: string | null
  metadata?: Record<string, any>
}

export interface AlertCreateRequest {
  level: AlertLevel
  source: string
  title: string
  detail: string
  metadata?: Record<string, any>
}

export interface AlertUpdateRequest {
  resolved: boolean
  resolvedAt?: string
}

export interface AlertListResponse {
  alerts: Alert[]
  total: number
  unresolved: number
}

export interface AlertStats {
  total: number
  resolved: number
  unresolved: number
  warnings: number
  errors: number
}
