// Ref: docs/api/api-design.md
// Axios-based API client for ArtClaw Tool Manager
import axios, { type AxiosInstance, type AxiosError } from 'axios'
import type {
  ApiResponse,
  SkillItem,
  WorkflowItem,
  ToolItem,
  SystemStatus,
  ChatSession,
  ChatMessage,
  WorkflowParameter,
  DCCStatusInfo,
  TriggerEngineStats,
  DCCEvent,
  FilterPreset,
  Alert,
  AlertCreateRequest,
  AlertUpdateRequest,
  AlertListResponse,
  AlertStats,
} from '../types'

// ---------- Axios Instance ----------

const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Unified error handler
api.interceptors.response.use(
  (res) => res,
  (error: AxiosError<{ error?: { code: string; message: string } }>) => {
    const msg = error.response?.data?.error?.message ?? error.message
    console.error('[API Error]', msg)
    return Promise.reject(error)
  },
)

// ---------- Skills ----------

export async function fetchSkills(params?: {
  source?: string
  targetDCC?: string
  search?: string
  installed?: boolean
  page?: number
  limit?: number
}): Promise<ApiResponse<SkillItem[]>> {
  const { data } = await api.get('/skills', { params })
  return data
}

export async function fetchSkillDetail(id: string): Promise<ApiResponse<SkillItem>> {
  const { data } = await api.get(`/skills/${encodeURIComponent(id)}`)
  return data
}

export async function installSkill(id: string, version?: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/skills/${encodeURIComponent(id)}/install`, { version })
  return data
}

export async function uninstallSkill(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/skills/${encodeURIComponent(id)}/uninstall`)
  return data
}

export async function updateSkill(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/skills/${encodeURIComponent(id)}/update`)
  return data
}

export async function enableSkill(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/skills/${encodeURIComponent(id)}/enable`)
  return data
}

export async function disableSkill(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/skills/${encodeURIComponent(id)}/disable`)
  return data
}

export async function pinSkill(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/skills/${encodeURIComponent(id)}/pin`)
  return data
}

export async function unpinSkill(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/skills/${encodeURIComponent(id)}/unpin`)
  return data
}

// ---------- Workflows ----------

export async function fetchWorkflows(params?: {
  source?: string
  targetDCC?: string
  search?: string
  page?: number
  limit?: number
}): Promise<ApiResponse<WorkflowItem[]>> {
  const { data } = await api.get('/workflows', { params })
  return data
}

export async function fetchWorkflowDetail(id: string): Promise<ApiResponse<WorkflowItem>> {
  const { data } = await api.get(`/workflows/${encodeURIComponent(id)}`)
  return data
}

export async function favoriteWorkflow(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/workflows/${encodeURIComponent(id)}/favorite`)
  return data
}

export async function unfavoriteWorkflow(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/workflows/${encodeURIComponent(id)}/unfavorite`)
  return data
}

// ---------- Tools ----------

export async function fetchTools(params?: {
  source?: string
  targetDCC?: string
  search?: string
  page?: number
  limit?: number
}): Promise<ApiResponse<ToolItem[]>> {
  const { data } = await api.get('/tools', { params })
  return data
}

export async function fetchToolDetail(id: string): Promise<ApiResponse<ToolItem>> {
  const { data } = await api.get(`/tools/${encodeURIComponent(id)}`)
  return data
}

export async function createTool(data: {
  name: string
  description?: string
  version?: string
  source?: string
  target_dccs?: string[]
  implementation_type?: string
  manifest?: Record<string, unknown>
}): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post('/tools', data)
  return resp
}

export async function updateTool(id: string, data: Record<string, unknown>): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.patch(`/tools/${encodeURIComponent(id)}`, data)
  return resp
}

export async function deleteTool(id: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.delete(`/tools/${encodeURIComponent(id)}`)
  return resp
}

export async function enableTool(id: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(id)}/enable`)
  return resp
}

export async function disableTool(id: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(id)}/disable`)
  return resp
}

export async function pinTool(id: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(id)}/pin`)
  return resp
}

export async function unpinTool(id: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(id)}/unpin`)
  return resp
}

export async function favoriteTool(id: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(id)}/favorite`)
  return resp
}

export async function unfavoriteTool(id: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(id)}/unfavorite`)
  return resp
}

export async function executeTool(id: string, parameters?: Record<string, unknown>): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(id)}/execute`, { parameters: parameters ?? {} })
  return resp
}

export async function batchToolOperation(operation: string, toolIds: string[]): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post('/tools/batch', { operation, tool_ids: toolIds })
  return resp
}

// ---------- Triggers ----------

/** Convert snake_case keys to camelCase (shallow, for API responses) */
function snakeToCamel(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, c) => c.toUpperCase())
    result[camelKey] = value
  }
  return result
}

export async function fetchTriggers(toolId: string): Promise<ApiResponse<unknown[]>> {
  const { data: resp } = await api.get(`/tools/${encodeURIComponent(toolId)}/triggers`)
  // Backend returns snake_case, frontend expects camelCase
  if (resp?.success && Array.isArray(resp.data)) {
    resp.data = resp.data.map((t: unknown) =>
      typeof t === 'object' && t !== null ? snakeToCamel(t as Record<string, unknown>) : t
    )
  }
  return resp
}

export async function createTrigger(toolId: string, data: Record<string, unknown>): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(toolId)}/triggers`, data)
  return resp
}

export async function updateTrigger(triggerId: string, data: Record<string, unknown>): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.patch(`/triggers/${triggerId}`, data)
  return resp
}

export async function deleteTrigger(triggerId: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.delete(`/triggers/${triggerId}`)
  return resp
}

export async function enableTrigger(triggerId: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/triggers/${triggerId}/enable`)
  return resp
}

export async function disableTrigger(triggerId: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/triggers/${triggerId}/disable`)
  return resp
}

// ---------- Presets ----------

export async function fetchPresets(toolId: string): Promise<ApiResponse<unknown[]>> {
  const { data: resp } = await api.get(`/tools/${encodeURIComponent(toolId)}/presets`)
  return resp
}

export async function createPreset(toolId: string, data: {
  name: string
  description?: string
  is_default?: boolean
  values?: Record<string, unknown>
}): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(toolId)}/presets`, data)
  return resp
}

export async function updatePreset(toolId: string, presetId: string, data: Record<string, unknown>): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.patch(`/tools/${encodeURIComponent(toolId)}/presets/${presetId}`, data)
  return resp
}

export async function deletePreset(toolId: string, presetId: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.delete(`/tools/${encodeURIComponent(toolId)}/presets/${presetId}`)
  return resp
}

export async function setDefaultPreset(toolId: string, presetId: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/tools/${encodeURIComponent(toolId)}/presets/${presetId}/set-default`)
  return resp
}

// ---------- Skills Sync ----------

export async function syncSkillFromSource(skillId: string): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(`/skills/${encodeURIComponent(skillId)}/sync-from-source`)
  return resp
}

export async function publishSkillToSource(
  skillId: string,
  options?: { version?: string; description?: string },
): Promise<ApiResponse<unknown>> {
  const { data: resp } = await api.post(
    `/skills/${encodeURIComponent(skillId)}/publish-to-source`,
    options ?? {},
  )
  return resp
}

// ---------- Sessions ----------

export async function fetchSessions(): Promise<ApiResponse<ChatSession[]>> {
  const { data } = await api.get('/sessions')
  return data
}

export async function createSession(name?: string): Promise<ApiResponse<ChatSession>> {
  const { data } = await api.post('/sessions', { name })
  return data
}

export async function fetchSessionMessages(
  sessionId: string,
): Promise<ApiResponse<ChatMessage[]>> {
  const { data } = await api.get(`/sessions/${sessionId}/messages`)
  return data
}

export async function deleteSession(sessionId: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.delete(`/sessions/${sessionId}`)
  return data
}

// ---------- System ----------

export async function fetchSystemStatus(): Promise<ApiResponse<SystemStatus>> {
  const { data } = await api.get('/system/status')
  return data
}

export async function fetchSystemConfig(): Promise<ApiResponse<Record<string, unknown>>> {
  const { data } = await api.get('/system/config')
  return data
}

export default api

// ---------- Workflows Extended ----------

export async function fetchWorkflowParameters(id: string): Promise<ApiResponse<WorkflowParameter[]>> {
  const { data } = await api.get(`/workflows/${encodeURIComponent(id)}/parameters`)
  return data
}

export async function executeWorkflow(id: string, params: Record<string, unknown>): Promise<ApiResponse<unknown>> {
  const { data } = await api.post(`/workflows/${encodeURIComponent(id)}/execute`, { parameters: params })
  return data
}

// ---------- Skills Recent ----------

export async function fetchRecentSkills(limit: number = 10): Promise<ApiResponse<unknown[]>> {
  const { data } = await api.get('/skills/recent', { params: { limit } })
  return data
}

export async function fetchRecentWorkflows(limit: number = 5): Promise<any[]> {
  const { data } = await api.get('/workflows/recent', { params: { limit } })
  return data?.data ?? []
}

export async function fetchRecentTools(limit: number = 5): Promise<any[]> {
  const { data } = await api.get('/tools/recent', { params: { limit } })
  return data?.data ?? []
}

// ---------- DCC Events (Phase 5) ----------

export async function fetchDCCStatus(): Promise<ApiResponse<Record<string, DCCStatusInfo>>> {
  const { data } = await api.get('/system/dcc-status')
  return data
}

export async function refreshDCCStatus(): Promise<ApiResponse<Record<string, DCCStatusInfo>>> {
  const { data } = await api.post('/system/dcc-status/refresh')
  return data
}

export async function fetchTriggerStats(): Promise<ApiResponse<TriggerEngineStats>> {
  const { data } = await api.get('/dcc-events/stats')
  return data
}

export async function postDCCEvent(event: DCCEvent): Promise<ApiResponse<unknown>> {
  const { data } = await api.post('/dcc-events', event)
  return data
}

// ---------- Filter Presets ----------

export async function fetchFilterPresets(dcc?: string): Promise<ApiResponse<FilterPreset[]>> {
  const { data } = await api.get('/filter-presets', { params: dcc ? { dcc } : {} })
  return data
}

export async function fetchFilterPreset(id: string): Promise<ApiResponse<FilterPreset>> {
  const { data } = await api.get(`/filter-presets/${encodeURIComponent(id)}`)
  return data
}

export async function createFilterPreset(preset: {
  name: string
  description?: string
  dcc?: string[]
  filter: Record<string, unknown>
}): Promise<ApiResponse<FilterPreset>> {
  const { data } = await api.post('/filter-presets', preset)
  return data
}

export async function updateFilterPreset(id: string, updates: Record<string, unknown>): Promise<ApiResponse<FilterPreset>> {
  const { data } = await api.patch(`/filter-presets/${encodeURIComponent(id)}`, updates)
  return data
}

export async function deleteFilterPreset(id: string): Promise<ApiResponse<unknown>> {
  const { data } = await api.delete(`/filter-presets/${encodeURIComponent(id)}`)
  return data
}

// ---------- Sessions Extended ----------

export async function updateSession(sessionId: string, updates: Record<string, unknown>): Promise<ApiResponse<ChatSession>> {
  const { data } = await api.patch(`/sessions/${sessionId}`, updates)
  return data
}

// ---------- Alerts ----------

export async function fetchAlerts(resolved?: boolean): Promise<AlertListResponse> {
  const params = resolved !== undefined ? { resolved } : {}
  const { data } = await api.get('/alerts', { params })
  return data
}

export async function createAlert(request: AlertCreateRequest): Promise<Alert> {
  const { data } = await api.post('/alerts', request)
  return data
}

export async function updateAlert(alertId: string, request: AlertUpdateRequest): Promise<Alert> {
  const { data } = await api.patch(`/alerts/${alertId}`, request)
  return data
}

export async function deleteAlert(alertId: string): Promise<void> {
  await api.delete(`/alerts/${alertId}`)
}

export async function getAlertStats(): Promise<AlertStats> {
  const { data } = await api.get('/alerts/stats')
  return data
}

export async function cleanupAlerts(days: number = 7): Promise<{ message: string; cleanedCount: number }> {
  const { data } = await api.post('/alerts/cleanup', null, { params: { days } })
  return data
}
