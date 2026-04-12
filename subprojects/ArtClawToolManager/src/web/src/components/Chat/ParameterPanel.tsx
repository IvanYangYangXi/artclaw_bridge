// Ref: docs/ui/ui-design.md#Chat
// Dynamic parameter form for workflow/tool execution
// Includes: parameter form, trigger rules (editable), filter display, preset quick-switch
import { useState, useEffect, useCallback } from 'react'
import { Play, RefreshCw, Upload, Image, Zap, Star, Plus, Trash2 } from 'lucide-react'
import { cn } from '../../utils/cn'
import type { WorkflowParameter, ExecutionContext, TriggerRuleData, ParameterPreset, ToolItemExtended } from '../../types'
import { DCC_DISPLAY_NAMES, DCC_EVENTS, getEventLabel } from '../../constants/dccTypes'
import { fetchTriggers, fetchPresets, createTrigger, deleteTrigger, updateTrigger, fetchToolDetail } from '../../api/client'
import { useAppStore } from '../../stores/appStore'

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
  const [newTriggerName, setNewTriggerName] = useState('')
  const [newTriggerType, setNewTriggerType] = useState<string>('manual')
  const [newTriggerDcc, setNewTriggerDcc] = useState('')
  const [newTriggerEvent, setNewTriggerEvent] = useState('')
  const [newTriggerTiming, setNewTriggerTiming] = useState<string>('post')
  const [newTriggerMode, setNewTriggerMode] = useState<string>('notify')
  
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

  const handleExecute = async () => {
    const mergedParams = { ...values }
    // Include temp input overrides
    if (Object.keys(tempInputOverrides).length > 0) {
      mergedParams._inputOverrides = tempInputOverrides
    }
    
    if (executionContext.needsAI === false) {
      try {
        await fetch(`/api/v1/tools/${executionContext.id}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parameters: mergedParams }),
        })
        onCancel()
      } catch (error) {
        console.error('Failed to execute tool:', error)
      }
    } else {
      // For AI execution, we need to update the store's values to include overrides
      // so they get included in the chat message
      if (Object.keys(tempInputOverrides).length > 0) {
        onChange('_inputOverrides', tempInputOverrides)
      }
      onSubmit()
    }
  }

  const handlePresetApply = (preset: ParameterPreset) => {
    for (const [key, value] of Object.entries(preset.values)) {
      onChange(key, value)
    }
  }

  const handleAddTrigger = async () => {
    try {
      const resp = await createTrigger(executionContext.id, {
        name: newTriggerName || (zh ? '新规则' : 'New Rule'),
        trigger_type: newTriggerType,
        dcc: newTriggerDcc || undefined,
        event_type: newTriggerEvent || undefined,
        event_timing: newTriggerTiming,
        execution_mode: newTriggerMode,
        is_enabled: true,
        conditions: {},
      })
      if (resp.success && resp.data) {
        setTriggers((prev) => [...prev, resp.data as TriggerRuleData])
      }
    } catch { /* ignore */ }
    setShowAddTrigger(false)
    setNewTriggerName('')
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

  const inputCls = 'w-full px-2 py-1.5 rounded bg-bg-tertiary text-text-primary text-[11px] border border-border-default focus:border-accent focus:outline-none placeholder:text-text-dim transition-colors'

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

        {/* ── Script Parameters (tool only, editable) ── */}
        {isTool && toolData?.manifest?.inputs && (toolData.manifest.inputs as Array<{ id: string; name: string; type: string; default?: unknown; description?: string; required?: boolean }>).length > 0 && (
          <div className="pt-2 border-t border-border-default">
            <label className="block text-[11px] text-text-dim mb-1.5 flex items-center gap-1">
              📦 {zh ? '脚本参数设置' : 'Script Parameter Settings'}
            </label>
            <div className="space-y-2">
              <p className="text-[10px] text-text-dim italic">{zh ? '临时调整（仅用于当前执行，不会永久保存）' : 'Temporary adjustments (current execution only, not saved permanently)'}</p>
              {(toolData.manifest.inputs as Array<{ id: string; name: string; type: string; default?: unknown; description?: string; required?: boolean }>).map((input) => {
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
        )}

        {/* ── Trigger Rules (tool only, editable) ── */}
        {isTool && (
          <div className="pt-2 border-t border-border-default">
            <label className="block text-[11px] text-text-dim mb-1.5 flex items-center justify-between">
              <span className="flex items-center gap-1"><Zap className="w-3 h-3" /> {zh ? '触发规则' : 'Trigger Rules'}</span>
              <button
                onClick={() => setShowAddTrigger(!showAddTrigger)}
                className="text-accent hover:text-accent-hover transition-colors"
                title={zh ? '添加规则' : 'Add Rule'}
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </label>

            {/* Existing triggers */}
            {triggers.length > 0 && (
              <div className="space-y-1.5 mb-2">
                {triggers.map((t) => {
                  const tAny = t as TriggerRuleData & { dcc?: string }
                  const dccName = tAny.dcc ? (DCC_DISPLAY_NAMES[tAny.dcc] ?? tAny.dcc) : ''
                  const eventLabel = tAny.dcc && t.eventType
                    ? getEventLabel(tAny.dcc, t.eventType, language)
                    : t.eventType
                  const isExpanded = expandedTriggerId === t.id
                  const conditions = t.conditions as Record<string, unknown> | undefined
                  const hasConditions = conditions && (
                    (conditions.fileRules as unknown[] | undefined)?.length ||
                    (conditions.sceneRules as unknown[] | undefined)?.length ||
                    conditions.typeFilter ||
                    conditions.pathGlob ||
                    conditions.nameRegex
                  )
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
                      {/* Expanded: show inline conditions */}
                      {isExpanded && (
                        <div className="px-2 pb-2 text-[10px] text-text-dim space-y-0.5">
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
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {triggers.length === 0 && !showAddTrigger && (
              <p className="text-[10px] text-text-dim mb-2">{zh ? '暂无触发规则，点 + 添加' : 'No rules. Click + to add'}</p>
            )}

            {/* Add trigger inline form */}
            {showAddTrigger && (
              <div className="border border-border-default rounded p-2 bg-bg-secondary space-y-1.5 mb-2">
                <input value={newTriggerName} onChange={(e) => setNewTriggerName(e.target.value)} placeholder={zh ? '规则名称' : 'Rule name'} className={inputCls} />
                <div className="flex gap-1 flex-wrap">
                  {(['manual', 'event', 'schedule', 'watch'] as const).map((tt) => (
                    <button key={tt} onClick={() => setNewTriggerType(tt)}
                      className={cn('px-2 py-0.5 rounded text-[10px] transition-colors',
                        newTriggerType === tt ? 'bg-accent text-white' : 'bg-bg-tertiary text-text-dim hover:text-text-secondary')}>
                      {TRIGGER_TYPE_LABEL[tt]}
                    </button>
                  ))}
                </div>
                {newTriggerType === 'event' && (
                  <div className="space-y-1">
                    <select value={newTriggerDcc} onChange={(e) => { setNewTriggerDcc(e.target.value); setNewTriggerEvent('') }} className={inputCls}>
                      <option value="">DCC</option>
                      {Object.keys(DCC_EVENTS).map((d) => <option key={d} value={d}>{DCC_DISPLAY_NAMES[d] ?? d}</option>)}
                    </select>
                    {newTriggerDcc && (
                      <select value={newTriggerEvent} onChange={(e) => setNewTriggerEvent(e.target.value)} className={inputCls}>
                        <option value="">{zh ? '事件类型' : 'Event'}</option>
                        {(DCC_EVENTS[newTriggerDcc] ?? []).map((e) => <option key={e.event} value={e.event}>{zh ? e.label : e.labelEn}</option>)}
                      </select>
                    )}
                    <div className="flex gap-1">
                      {['pre', 'post'].map((t) => (
                        <button key={t} onClick={() => setNewTriggerTiming(t)}
                          className={cn('px-2 py-0.5 rounded text-[10px] transition-colors',
                            newTriggerTiming === t ? 'bg-accent text-white' : 'bg-bg-tertiary text-text-dim')}>
                          {t === 'pre' ? (zh ? '事件前' : 'Before') : (zh ? '事件后' : 'After')}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex gap-1 flex-wrap">
                  {(['silent', 'notify', 'interactive'] as const).map((m) => (
                    <button key={m} onClick={() => setNewTriggerMode(m)}
                      className={cn('px-2 py-0.5 rounded text-[10px] transition-colors',
                        newTriggerMode === m ? 'bg-accent text-white' : 'bg-bg-tertiary text-text-dim')}>
                      {EXEC_MODE_LABEL[m]}
                    </button>
                  ))}
                </div>
                <div className="flex gap-1.5 pt-1">
                  <button onClick={handleAddTrigger} className="px-2 py-1 rounded text-[10px] bg-accent text-white hover:bg-accent/90">{zh ? '添加' : 'Add'}</button>
                  <button onClick={() => setShowAddTrigger(false)} className="px-2 py-1 rounded text-[10px] text-text-dim hover:bg-bg-tertiary">{zh ? '取消' : 'Cancel'}</button>
                </div>
              </div>
            )}

            {/* Tip */}
            <p className="text-[10px] text-text-dim italic">
              {zh ? '💡 完整筛选条件编辑请进入工具详情面板' : '💡 Full filter editing in tool detail panel'}
            </p>
          </div>
        )}
      </div>

      {/* Hint */}
      <div className="shrink-0 px-4 py-2">
        <p className="text-[11px] text-text-dim">
          {zh
            ? '💡 你可以说"帮我填写参数"让 AI 协助'
            : '💡 Say "help me fill parameters" to get AI assistance'}
        </p>
      </div>

      {/* Actions */}
      <div className="shrink-0 px-4 py-3 border-t border-border-default flex items-center gap-2">
        <button
          onClick={handleExecute}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded text-small font-medium bg-accent text-white hover:bg-accent/90 transition-colors"
        >
          <Play className="w-3.5 h-3.5" />
          {zh ? '执行' : 'Execute'}
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
