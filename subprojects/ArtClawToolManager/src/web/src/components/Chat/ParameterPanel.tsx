// Ref: docs/ui/ui-design.md#Chat
// Dynamic parameter form for workflow/tool execution
// Includes: parameter form, trigger rules (editable), filter display, preset quick-switch
import { useState, useEffect, useCallback } from 'react'
import { Play, RefreshCw, Upload, Image, Zap, Star, Plus, Trash2, ChevronDown, ChevronRight, Loader2, AlertTriangle, X } from 'lucide-react'
import { cn } from '../../utils/cn'
import type { WorkflowParameter, ExecutionContext, TriggerRuleData, ParameterPreset, ToolItemExtended } from '../../types'
import { DCC_DISPLAY_NAMES, getEventLabel } from '../../constants/dccTypes'
import { fetchTriggers, fetchPresets, createTrigger, deleteTrigger, updateTrigger, fetchToolDetail } from '../../api/client'
import { useAppStore } from '../../stores/appStore'
import TriggerRuleEditor, { type TriggerFormData } from '../Tools/TriggerRuleEditor'

interface ParameterPanelProps {
  executionContext: ExecutionContext
  workflowName: string
  parameters: WorkflowParameter[]
  values: Record<string, unknown>
  onChange: (id: string, value: unknown) => void
  onSubmit: () => void
  onCancel: () => void
  onReset: () => void
}

export default function ParameterPanel({
  executionContext,
  workflowName,
  parameters,
  values,
  onChange,
  onSubmit,
  onCancel,
  onReset,
}: ParameterPanelProps) {
  const language = useAppStore((s) => s.language)
  const zh = language === 'zh'
  const [triggers, setTriggers] = useState<TriggerRuleData[]>([])
  const [presets, setPresets] = useState<ParameterPreset[]>([])
  const [toolData, setToolData] = useState<ToolItemExtended | null>(null)
  const [expandedTriggerId, setExpandedTriggerId] = useState<string | null>(null)
  const [showAddTrigger, setShowAddTrigger] = useState(false)
  const [triggerSectionExpanded, setTriggerSectionExpanded] = useState(true)
  
  // Temporary overrides for script parameter defaults (not saved permanently)
  const [tempInputOverrides, setTempInputOverrides] = useState<Record<string, { name?: string; default?: unknown; description?: string; required?: boolean }>>({})

  const isTool = executionContext.type === 'tool'

  // Load triggers and presets for tool context
  const loadData = useCallback(() => {
    if (!isTool) return
    fetchTriggers(executionContext.id)
      .then((r) => { if (r.success) setTriggers((r.data ?? []) as TriggerRuleData[]) })
      .catch(() => setTriggers([]))
    fetchPresets(executionContext.id)
      .then((r) => { if (r.success) setPresets((r.data ?? []) as ParameterPreset[]) })
      .catch(() => setPresets([]))
    // Fetch tool data for manifest
    fetchToolDetail(executionContext.id)
      .then((r) => { if (r.success) setToolData(r.data as ToolItemExtended) })
      .catch(() => setToolData(null))
  }, [executionContext.id, isTool])

  useEffect(() => { loadData() }, [loadData])

  const [executing, setExecuting] = useState(false)
  // DCC connection check dialog state
  const [dccNotConnected, setDccNotConnected] = useState<{ dccNames: string[] } | null>(null)
  const dccOptions = useAppStore((s) => s.dccOptions)

  /**
   * Check if the tool's target DCCs are connected via MCP.
   * Returns the list of disconnected DCC display names, or empty if all OK.
   */
  const checkDCCConnection = useCallback((): string[] => {
    // Determine target DCCs from toolData manifest or executionContext
    const targetDCCs: string[] = toolData?.manifest?.targetDCCs ?? []
    // Filter out "general" — general tools don't need DCC
    const realTargets = targetDCCs.filter((d) => d && d !== 'general')
    if (realTargets.length === 0) return []

    const disconnected: string[] = []
    for (const dcc of realTargets) {
      const opt = dccOptions.find((o) => o.id === dcc)
      if (!opt || !opt.connected) {
        disconnected.push(DCC_DISPLAY_NAMES[dcc] || dcc)
      }
    }
    return disconnected
  }, [toolData, dccOptions])

  const handleExecute = async () => {
    if (executing) return

    // Pre-flight: check DCC connection for DCC-bound tools
    if (executionContext.needsAI === false) {
      const disconnected = checkDCCConnection()
      if (disconnected.length > 0) {
        setDccNotConnected({ dccNames: disconnected })
        return
      }
    }

    setExecuting(true)

    const mergedParams = { ...values }
    if (Object.keys(tempInputOverrides).length > 0) {
      mergedParams._inputOverrides = tempInputOverrides
    }

    const { addMessage } = (await import('../../stores/chatStore')).useChatStore.getState()
    
    if (executionContext.needsAI === false) {
      try {
        const res = await fetch(`/api/v1/tools/${encodeURIComponent(executionContext.id)}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parameters: mergedParams }),
        })
        const data = await res.json() as {
          success: boolean
          data?: { action?: string; exit_code?: number; stdout?: string; stderr?: string; success?: boolean; command?: string }
          detail?: { message?: string; code?: string }
        }

        if (data.success && data.data?.action === 'executed') {
          const r = data.data
          const icon = r.success ? '✅' : '❌'
          const lines = [
            `${icon} **${executionContext.name}** 执行${r.success ? '完成' : '失败'} (exit ${r.exit_code})`,
          ]
          if (r.stdout?.trim()) lines.push(`\`\`\`\n${r.stdout.trim()}\n\`\`\``)
          if (r.stderr?.trim()) lines.push(`⚠️ stderr:\n\`\`\`\n${r.stderr.trim()}\n\`\`\``)
          addMessage({
            id: `exec-${Date.now()}`,
            role: 'system',
            content: lines.join('\n\n'),
            timestamp: new Date().toISOString(),
          })
          onCancel()
        } else if (data.success && data.data?.action === 'navigate') {
          // AI-driven tool from direct execute endpoint – submit to chat
          onSubmit()
        } else {
          // Backend returned an error response
          const errCode = data.detail?.code || ''
          const errMsg = data.detail?.message || JSON.stringify(data)
          
          // Special handling for DCC not connected
          if (errCode === 'DCC_NOT_CONNECTED') {
            const disconnected = checkDCCConnection()
            setDccNotConnected({ dccNames: disconnected.length > 0 ? disconnected : [errMsg] })
          } else {
            addMessage({
              id: `exec-err-${Date.now()}`,
              role: 'system',
              content: `❌ **${executionContext.name}** 执行失败: ${errMsg}`,
              timestamp: new Date().toISOString(),
            })
          }
          // Don't close panel on error — let user retry
        }
      } catch (error) {
        console.error('Failed to execute tool:', error)
        addMessage({
          id: `exec-err-${Date.now()}`,
          role: 'system',
          content: `❌ **${executionContext.name}** 执行失败: ${error instanceof Error ? error.message : '网络错误'}`,
          timestamp: new Date().toISOString(),
        })
      }
    } else {
      if (Object.keys(tempInputOverrides).length > 0) {
        onChange('_inputOverrides', tempInputOverrides)
      }
      onSubmit()
    }
    setExecuting(false)
  }

  const handlePresetApply = (preset: ParameterPreset) => {
    for (const [key, value] of Object.entries(preset.values)) {
      onChange(key, value)
    }
  }

  const handleAddTrigger = async (data: TriggerFormData) => {
    try {
      const resp = await createTrigger(executionContext.id, {
        name: data.name || (zh ? '新规则' : 'New Rule'),
        trigger_type: data.triggerType,
        dcc: data.dcc || undefined,
        event_type: data.eventType || undefined,
        event_timing: data.eventTiming,
        execution_mode: data.executionMode,
        is_enabled: data.isEnabled,
        conditions: data.conditions,
        parameter_preset_id: data.parameterPresetId,
        schedule_config: data.scheduleConfig,
      })
      if (resp.success && resp.data) {
        setTriggers((prev) => [...prev, resp.data as TriggerRuleData])
      }
    } catch { /* ignore */ }
    setShowAddTrigger(false)
  }

  const handleDeleteTrigger = async (id: string) => {
    try {
      await deleteTrigger(id)
      setTriggers((prev) => prev.filter((t) => t.id !== id))
    } catch { /* ignore */ }
  }

  const handleToggleTrigger = async (t: TriggerRuleData) => {
    try {
      await updateTrigger(t.id, { is_enabled: !t.isEnabled })
      setTriggers((prev) => prev.map((tr) => tr.id === t.id ? { ...tr, isEnabled: !tr.isEnabled } : tr))
    } catch { /* ignore */ }
  }

  const TRIGGER_TYPE_LABEL: Record<string, string> = zh
    ? { manual: '手动', event: '事件', schedule: '定时', watch: '监听' }
    : { manual: 'Manual', event: 'Event', schedule: 'Schedule', watch: 'Watch' }

  const EXEC_MODE_LABEL: Record<string, string> = zh
    ? { silent: '静默', notify: '通知', interactive: '交互(AI)' }
    : { silent: 'Silent', notify: 'Notify', interactive: 'Interactive' }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-4 py-3 border-b border-border-default">
        <h3 className="text-small font-medium text-text-primary truncate">{workflowName}</h3>
        <p className="text-[11px] text-text-dim mt-0.5">{zh ? '配置参数' : 'Configure Parameters'}</p>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {/* Preset quick-switch */}
        {presets.length > 0 && (
          <div>
            <label className="block text-[11px] text-text-dim mb-1.5 flex items-center gap-1">
              <Star className="w-3 h-3" /> {zh ? '预设' : 'Presets'}
            </label>
            <div className="flex flex-wrap gap-1.5">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => handlePresetApply(preset)}
                  className={cn(
                    'text-[11px] px-2 py-1 rounded border cursor-pointer transition-colors',
                    preset.isDefault
                      ? 'bg-accent/20 text-accent border-accent/50 hover:bg-accent/30'
                      : 'bg-bg-tertiary text-text-secondary border-border-default hover:bg-bg-quaternary hover:text-text-primary',
                  )}
                  title={preset.description ?? preset.name}
                >
                  {preset.isDefault && '★ '}
                  {preset.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Parameter fields */}
        {parameters.map((param) => (
          <ParameterField
            key={param.id}
            param={param}
            value={values[param.id]}
            onChange={(val) => onChange(param.id, val)}
          />
        ))}

        {parameters.length === 0 && (
          <div className="flex flex-col items-center justify-center py-6 text-text-dim">
            <p className="text-small">{zh ? '此项目无需配置参数' : 'No parameters needed'}</p>
          </div>
        )}

        {/* ── Script Parameters (tool only, editable meta-info) ── */}
        {/* Hidden when executionContext.parameters already covers all manifest inputs.
            Only shown when there are extra script-level inputs not in the parameters above. */}
        {isTool && toolData?.manifest?.inputs && (() => {
          const manifestInputs = toolData.manifest.inputs as Array<{ id: string; name: string; type: string; default?: unknown; description?: string; required?: boolean }>
          const paramIds = new Set(parameters.map((p) => p.id))
          const extraInputs = manifestInputs.filter((inp) => !paramIds.has(inp.id))
          if (extraInputs.length === 0) return null
          return (
            <div className="pt-2 border-t border-border-default">
              <label className="block text-[11px] text-text-dim mb-1.5 flex items-center gap-1">
                📦 {zh ? '脚本参数设置' : 'Script Parameter Settings'}
              </label>
              <div className="space-y-2">
                <p className="text-[10px] text-text-dim italic">{zh ? '临时调整（仅用于当前执行，不会永久保存）' : 'Temporary adjustments (current execution only, not saved permanently)'}</p>
                {extraInputs.map((input) => {
                  const override = tempInputOverrides[input.id] || {}
                  const currentName = override.name ?? input.name
                  const currentDefault = override.default !== undefined ? override.default : input.default
                  const currentDescription = override.description ?? input.description
                  const currentRequired = override.required ?? input.required
                  
                  return (
                    <div key={input.id} className="bg-bg-tertiary rounded border border-border-default/50 p-2 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={currentName}
                          onChange={(e) => setTempInputOverrides(prev => ({
                            ...prev,
                            [input.id]: { ...prev[input.id], name: e.target.value }
                          }))}
                          className="flex-1 px-2 py-1 rounded bg-bg-secondary text-text-primary text-[11px] border border-border-default focus:border-accent focus:outline-none"
                          placeholder="Parameter name"
                        />
                        <span className="px-1 py-0.5 bg-bg-quaternary rounded text-[10px] text-text-dim shrink-0">{input.type}</span>
                        <label className="flex items-center gap-1 text-[10px] text-text-dim">
                          <input
                            type="checkbox"
                            checked={currentRequired}
                            onChange={(e) => setTempInputOverrides(prev => ({
                              ...prev,
                              [input.id]: { ...prev[input.id], required: e.target.checked }
                            }))}
                            className="w-3 h-3"
                          />
                          {zh ? '必需' : 'Required'}
                        </label>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-text-dim shrink-0">{zh ? '默认值:' : 'Default:'}</span>
                        <input
                          type="text"
                          value={currentDefault !== undefined ? String(currentDefault) : ''}
                          onChange={(e) => setTempInputOverrides(prev => ({
                            ...prev,
                            [input.id]: { ...prev[input.id], default: e.target.value }
                          }))}
                          className="flex-1 px-2 py-1 rounded bg-bg-secondary text-text-primary text-[11px] border border-border-default focus:border-accent focus:outline-none"
                          placeholder={zh ? '默认值' : 'Default value'}
                        />
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-[10px] text-text-dim shrink-0 mt-1">{zh ? '描述:' : 'Description:'}</span>
                        <textarea
                          value={currentDescription || ''}
                          onChange={(e) => setTempInputOverrides(prev => ({
                            ...prev,
                            [input.id]: { ...prev[input.id], description: e.target.value }
                          }))}
                          rows={2}
                          className="flex-1 px-2 py-1 rounded bg-bg-secondary text-text-primary text-[11px] border border-border-default focus:border-accent focus:outline-none resize-y"
                          placeholder={zh ? '参数描述' : 'Parameter description'}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })()}

        {/* ── Trigger Rules (tool only, editable — full editor matching detail dialog) ── */}
        {isTool && (
          <div className="pt-2 border-t border-border-default">
            <button
              onClick={() => setTriggerSectionExpanded(!triggerSectionExpanded)}
              className="w-full flex items-center justify-between text-[11px] text-text-dim mb-1.5"
            >
              <span className="flex items-center gap-1">
                <Zap className="w-3 h-3" /> {zh ? '触发规则' : 'Trigger Rules'}
                {triggers.length > 0 && (
                  <span className="px-1.5 py-0.5 bg-bg-tertiary rounded-full text-[10px]">{triggers.length}</span>
                )}
              </span>
              {triggerSectionExpanded
                ? <ChevronDown className="w-3.5 h-3.5" />
                : <ChevronRight className="w-3.5 h-3.5" />}
            </button>

            {triggerSectionExpanded && (
              <>
                {/* Existing triggers */}
                {triggers.length > 0 && (
                  <div className="space-y-1.5 mb-2">
                    {triggers.map((t) => {
                      const tAny = t as TriggerRuleData & { dcc?: string; parameterPresetId?: string }
                      const dccName = tAny.dcc ? (DCC_DISPLAY_NAMES[tAny.dcc] ?? tAny.dcc) : ''
                      const eventLabel = tAny.dcc && t.eventType
                        ? getEventLabel(tAny.dcc, t.eventType, language)
                        : t.eventType
                      const isExpanded = expandedTriggerId === t.id
                      const ppName = tAny.parameterPresetId ? presets.find((p) => p.id === tAny.parameterPresetId)?.name : undefined
                      const conditions = t.conditions as Record<string, unknown> | undefined
                      const hasConditions = conditions && (
                        (conditions.fileRules as unknown[] | undefined)?.length ||
                        (conditions.sceneRules as unknown[] | undefined)?.length ||
                        conditions.typeFilter ||
                        conditions.pathGlob ||
                        conditions.nameRegex
                      )
                      const scheduleConfig = t.scheduleConfig as Record<string, unknown> | undefined
                      return (
                        <div key={t.id} className="bg-bg-tertiary rounded border border-border-default/50">
                          <div className="flex items-center gap-1.5 px-2 py-1.5">
                            <button
                              onClick={() => handleToggleTrigger(t)}
                              className={cn('w-2 h-2 rounded-full shrink-0 cursor-pointer transition-colors', t.isEnabled ? 'bg-success' : 'bg-text-dim')}
                              title={t.isEnabled ? (zh ? '点击禁用' : 'Disable') : (zh ? '点击启用' : 'Enable')}
                            />
                            <button
                              onClick={() => setExpandedTriggerId(isExpanded ? null : t.id)}
                              className="flex-1 min-w-0 text-left"
                            >
                              <span className="text-[11px] text-text-primary truncate block">{t.name || (zh ? '未命名' : 'Unnamed')}</span>
                              <span className="text-[10px] text-text-dim">
                                {TRIGGER_TYPE_LABEL[t.triggerType] ?? t.triggerType}
                                {dccName && ` · ${dccName}`}
                                {eventLabel && ` · ${eventLabel}`}
                                {t.eventTiming && ` (${t.eventTiming})`}
                                {` · ${EXEC_MODE_LABEL[t.executionMode] ?? t.executionMode}`}
                              </span>
                            </button>
                            <button
                              onClick={() => handleDeleteTrigger(t.id)}
                              className="p-1 rounded text-text-dim hover:text-error transition-colors shrink-0"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                          {/* Expanded: show full details */}
                          {isExpanded && (
                            <div className="px-2 pb-2 text-[10px] text-text-dim space-y-1">
                              {/* Schedule config */}
                              {t.triggerType === 'schedule' && scheduleConfig && (
                                <div className="flex items-center gap-1">
                                  <span>⏱</span>
                                  {scheduleConfig.type === 'interval' && <span>{zh ? '间隔' : 'Every'}: {String(scheduleConfig.interval || '')}</span>}
                                  {scheduleConfig.type === 'cron' && <span>Cron: {String(scheduleConfig.cron || '')}</span>}
                                  {scheduleConfig.type === 'once' && <span>{zh ? '执行时间' : 'At'}: {String(scheduleConfig.runAt || '')}</span>}
                                </div>
                              )}
                              {/* Conditions */}
                              {hasConditions ? (
                                <>
                                  {conditions.pathGlob && <div>📁 {String(conditions.pathGlob)}</div>}
                                  {conditions.nameRegex && <div>📝 {String(conditions.nameRegex)}</div>}
                                  {(conditions.fileRules as Array<{ pattern: string }> | undefined)?.map((r, i) => <div key={i}>📁 {r.pattern}</div>)}
                                  {(conditions.sceneRules as Array<{ pattern: string; isRegex?: boolean }> | undefined)?.map((r, i) => <div key={i}>🎯 {r.pattern}{r.isRegex ? ' (regex)' : ''}</div>)}
                                  {conditions.typeFilter && <div>📦 {((conditions.typeFilter as { types?: string[] }).types ?? []).join(', ')}</div>}
                                </>
                              ) : (
                                <span className="italic">{zh ? '无筛选条件（对所有对象生效）' : 'No filter (applies to all)'}</span>
                              )}
                              {/* Parameter preset reference */}
                              {ppName && <div>⭐ {zh ? '参数预设' : 'Preset'}: {ppName}</div>}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}

                {triggers.length === 0 && !showAddTrigger && (
                  <p className="text-[10px] text-text-dim mb-2">{zh ? '暂无触发规则' : 'No trigger rules yet'}</p>
                )}

                {/* Add trigger — use full TriggerRuleEditor */}
                {showAddTrigger ? (
                  <div className="mb-2">
                    <TriggerRuleEditor
                      parameterPresets={presets.map((p) => ({ id: p.id, name: p.name }))}
                      onSave={handleAddTrigger}
                      onCancel={() => setShowAddTrigger(false)}
                    />
                  </div>
                ) : (
                  <button
                    onClick={() => setShowAddTrigger(true)}
                    className="flex items-center gap-1 text-[12px] text-accent hover:text-accent-hover transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />{zh ? '添加规则' : 'Add Rule'}
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Hint */}
      <div className="shrink-0 px-4 py-2">
        <p className="text-[11px] text-text-dim">
          {executionContext.needsAI
            ? (zh
              ? '💡 此工具需要 AI 协助执行，请在对话面板中发送消息'
              : '💡 This tool requires AI to execute. Please use the chat panel.')
            : (zh
              ? '💡 你可以说"帮我填写参数"让 AI 协助'
              : '💡 Say "help me fill parameters" to get AI assistance')}
        </p>
      </div>

      {/* Actions */}
      <div className="shrink-0 px-4 py-3 border-t border-border-default flex items-center gap-2">
        <button
          onClick={executionContext.needsAI ? onSubmit : handleExecute}
          disabled={executing}
          className={cn(
            'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded text-small font-medium transition-colors disabled:opacity-50 disabled:cursor-wait',
            executionContext.needsAI
              ? 'bg-bg-tertiary text-text-secondary hover:bg-bg-quaternary hover:text-text-primary border border-border-default'
              : 'bg-accent text-white hover:bg-accent/90',
          )}
        >
          {executing
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Play className="w-3.5 h-3.5" />}
          {executing
            ? (zh ? '执行中...' : 'Executing...')
            : executionContext.needsAI
              ? (zh ? '发送到对话' : 'Send to Chat')
              : (zh ? '执行' : 'Execute')}
        </button>
        <button
          onClick={onReset}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded text-small text-text-secondary hover:bg-bg-tertiary hover:text-text-primary transition-colors"
          title={zh ? '重置参数' : 'Reset Parameters'}
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={onCancel}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded text-small text-text-secondary hover:bg-bg-tertiary hover:text-text-primary transition-colors"
          title={zh ? '取消' : 'Cancel'}
        >
          {zh ? '取消' : 'Cancel'}
        </button>
      </div>

      {/* DCC Not Connected Dialog */}
      {dccNotConnected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-bg-secondary rounded-lg shadow-xl border border-border-default w-[380px] max-w-[90vw]">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border-default">
              <AlertTriangle className="w-5 h-5 text-warning shrink-0" />
              <h3 className="text-small font-medium text-text-primary">
                {zh ? 'DCC 未连接' : 'DCC Not Connected'}
              </h3>
              <button
                onClick={() => setDccNotConnected(null)}
                className="ml-auto text-text-dim hover:text-text-secondary transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="px-4 py-4">
              <p className="text-small text-text-secondary mb-3">
                {zh
                  ? `此工具需要连接 ${dccNotConnected.dccNames.join('、')} 才能执行。`
                  : `This tool requires ${dccNotConnected.dccNames.join(', ')} to be connected.`}
              </p>
              <p className="text-small text-text-dim">
                {zh
                  ? '请先打开对应的 DCC 软件，并确认 ArtClaw Bridge 插件已加载且 MCP 服务已启动。'
                  : 'Please open the DCC application and ensure the ArtClaw Bridge plugin is loaded with MCP service running.'}
              </p>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border-default">
              <button
                onClick={async () => {
                  setDccNotConnected(null)
                  // Refresh DCC status
                  try {
                    await fetch('/api/v1/system/dcc-status/refresh', { method: 'POST' })
                    await useAppStore.getState().fetchDCCOptions()
                  } catch { /* ignore */ }
                }}
                className="px-3 py-1.5 rounded text-small text-accent hover:bg-bg-tertiary transition-colors"
              >
                {zh ? '刷新连接状态' : 'Refresh Status'}
              </button>
              <button
                onClick={() => setDccNotConnected(null)}
                className="px-3 py-1.5 rounded text-small bg-accent text-white hover:bg-accent/90 transition-colors"
              >
                {zh ? '知道了' : 'OK'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------- Field renderer ----------

function ParameterField({
  param,
  value,
  onChange,
}: {
  param: WorkflowParameter
  value: unknown
  onChange: (val: unknown) => void
}) {
  const language = useAppStore((s) => s.language)
  const label = (
    <label className="block text-small text-text-secondary mb-1">
      {param.name}
      {param.required && <span className="text-error ml-0.5">*</span>}
    </label>
  )

  const description = param.description && (
    <p className="text-[11px] text-text-dim mt-1">{param.description}</p>
  )

  switch (param.type) {
    case 'string':
      return (
        <div>
          {label}
          {param.multiline ? (
            <textarea
              value={(value as string) ?? (param.default as string) ?? ''}
              onChange={(e) => onChange(e.target.value)}
              placeholder={param.placeholder ?? ''}
              rows={3}
              className="w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small border border-border-default focus:border-accent focus:outline-none placeholder:text-text-dim resize-y transition-colors"
            />
          ) : (
            <input
              type="text"
              value={(value as string) ?? (param.default as string) ?? ''}
              onChange={(e) => onChange(e.target.value)}
              placeholder={param.placeholder ?? ''}
              className="w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small border border-border-default focus:border-accent focus:outline-none placeholder:text-text-dim transition-colors"
            />
          )}
          {description}
        </div>
      )

    case 'number':
      return (
        <div>
          {label}
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={(value as number) ?? (param.default as number) ?? ''}
              onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))}
              min={param.min}
              max={param.max}
              step={param.step ?? 1}
              className="flex-1 px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small border border-border-default focus:border-accent focus:outline-none placeholder:text-text-dim transition-colors"
            />
            {param.min !== undefined && param.max !== undefined && (
              <input
                type="range"
                value={(value as number) ?? (param.default as number) ?? param.min}
                onChange={(e) => onChange(Number(e.target.value))}
                min={param.min}
                max={param.max}
                step={param.step ?? 1}
                className="flex-1 accent-accent h-1.5"
              />
            )}
          </div>
          {(param.min !== undefined || param.max !== undefined) && (
            <p className="text-[11px] text-text-dim mt-1">
              {param.min !== undefined && (language === 'zh' ? `最小: ${param.min}` : `Min: ${param.min}`)}
              {param.min !== undefined && param.max !== undefined && ' · '}
              {param.max !== undefined && (language === 'zh' ? `最大: ${param.max}` : `Max: ${param.max}`)}
            </p>
          )}
          {description}
        </div>
      )

    case 'boolean':
      return (
        <div>
          <div className="flex items-center justify-between">
            <label className="text-small text-text-secondary">
              {param.name}
              {param.required && <span className="text-error ml-0.5">*</span>}
            </label>
            <button
              onClick={() => onChange(!(value ?? param.default ?? false))}
              className={cn(
                'relative w-9 h-5 rounded-full transition-colors',
                (value ?? param.default) ? 'bg-accent' : 'bg-bg-tertiary border border-border-default',
              )}
            >
              <span
                className={cn(
                  'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform',
                  (value ?? param.default) ? 'left-[18px]' : 'left-0.5',
                )}
              />
            </button>
          </div>
          {description}
        </div>
      )

    case 'enum':
    case 'select':
      return (
        <div>
          {label}
          <select
            value={(value as string) ?? (param.default as string) ?? ''}
            onChange={(e) => onChange(e.target.value)}
            className="w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small border border-border-default focus:border-accent focus:outline-none transition-colors appearance-none cursor-pointer"
          >
            <option value="" disabled>
              {language === 'zh' ? '请选择...' : 'Select...'}
            </option>
            {param.options?.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
          {description}
        </div>
      )

    case 'image':
      return (
        <div>
          {label}
          <div
            className="w-full h-24 rounded border border-dashed border-border-default bg-bg-tertiary flex flex-col items-center justify-center gap-1 cursor-pointer hover:border-border-hover transition-colors"
            onClick={() => { /* TODO: file picker */ }}
          >
            {value ? (
              <Image className="w-6 h-6 text-success" />
            ) : (
              <>
                <Upload className="w-5 h-5 text-text-dim" />
                <span className="text-[11px] text-text-dim">{language === 'zh' ? '点击上传图片' : 'Click to upload image'}</span>
              </>
            )}
          </div>
          {description}
        </div>
      )

    default:
      return null
  }
}
