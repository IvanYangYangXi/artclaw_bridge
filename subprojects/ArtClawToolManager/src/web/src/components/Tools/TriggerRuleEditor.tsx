// Ref: docs/features/phase4-tool-api.md#TriggerRules
// Trigger rule editor: type, event, timing, mode, conditions, presets, schedule
// Phase 6: DCC-grouped events, filter preset references, i18n
import { useState, useEffect, useRef } from 'react'
import { X, Plus, Trash2 } from 'lucide-react'
import { cn } from '../../utils/cn'
import { DCC_EVENTS, DCC_DISPLAY_NAMES, DCC_TYPE_PRESETS } from '../../constants/dccTypes'
import { useAppStore } from '../../stores/appStore'
import PathVariablesHelp from '../common/PathVariablesHelp'
import type { TriggerType, ExecutionMode, FilterConfig } from '../../types'

interface TriggerRuleEditorProps {
  initialData?: TriggerFormData
  parameterPresets?: Array<{ id: string; name: string }>
  defaultFilters?: FilterConfig   // Tool-level default filter conditions
  onSave?: (data: TriggerFormData) => void
  onChange?: (data: TriggerFormData) => void
  onCancel?: () => void
}

export interface TriggerFormData {
  name: string
  triggerType: TriggerType
  dcc: string
  eventType: string   // full value incl. timing suffix, e.g. "asset.save.pre", "file.save.post"
  executionMode: ExecutionMode
  useDefaultFilters: boolean
  conditions: FilterConfig
  parameterPreset: Array<{ key: string; value: string }>
  parameterPresetId: string
  isEnabled: boolean
  scheduleConfig: { type: string; interval?: string; cron?: string; runAt?: string }
}

const TRIGGER_TYPES: { value: TriggerType; labelZh: string; labelEn: string }[] = [
  { value: 'event', labelZh: '事件触发', labelEn: 'Event' },
  { value: 'schedule', labelZh: '定时触发', labelEn: 'Schedule' },
  { value: 'watch', labelZh: '文件监听', labelEn: 'Watch' },
]

const EXECUTION_MODES: { value: ExecutionMode; labelZh: string; labelEn: string; descZh: string; descEn: string }[] = [
  { value: 'silent',      labelZh: '静默',   labelEn: 'Silent',      descZh: '拦截保存 + 右下角气泡提示（UE 系统"无法保存"对话框仍会出现，无法消除）', descEn: 'Block save + toast notification (UE system dialog cannot be suppressed)' },
  { value: 'notify',      labelZh: '通知',   labelEn: 'Notify',      descZh: '拦截保存 + 弹出 ArtClaw 说明对话框（UE 系统"无法保存"对话框仍会出现）',   descEn: 'Block save + ArtClaw modal dialog (UE system dialog cannot be suppressed)' },
  { value: 'interactive', labelZh: '交互',   labelEn: 'Interactive', descZh: '不自动执行，触发时跳转到 Chat 页面由 AI 协助',  descEn: 'Navigate to Chat for AI-assisted handling instead of auto-running' },
]

const SCHEDULE_TYPES: { value: string; labelZh: string; labelEn: string }[] = [
  { value: 'interval', labelZh: '定时间隔', labelEn: 'Interval' },
  { value: 'cron', labelZh: 'Cron 表达式', labelEn: 'Cron Expression' },
  { value: 'once', labelZh: '单次执行', labelEn: 'Run Once' },
]

const DEFAULT_FORM: TriggerFormData = {
  name: '',
  triggerType: 'event',
  dcc: '',
  eventType: '',
  executionMode: 'notify',
  useDefaultFilters: true,
  conditions: { fileRules: [], sceneRules: [], typeFilter: undefined },
  parameterPreset: [],
  parameterPresetId: '',
  isEnabled: true,
  scheduleConfig: { type: 'interval', interval: '30m' },
}

export default function TriggerRuleEditor({
  initialData,
  parameterPresets,
  defaultFilters,
  onSave,
  onChange,
  onCancel,
}: TriggerRuleEditorProps) {
  const [form, setForm] = useState<TriggerFormData>(() => ({
    ...DEFAULT_FORM,
    ...initialData,
    dcc: initialData?.dcc ?? DEFAULT_FORM.dcc,
    parameterPresetId: initialData?.parameterPresetId ?? DEFAULT_FORM.parameterPresetId,
  }))

  const language = useAppStore((s) => s.language)

  // Filter condition state
  const [filterFileRules, setFilterFileRules] = useState('')
  const [filterSceneRules, setFilterSceneRules] = useState('')
  const [filterTypes, setFilterTypes] = useState<string[]>([])
  const [filterCustomTypes, setFilterCustomTypes] = useState('')
  const [filterIsRegex, setFilterIsRegex] = useState(false)
  const [filterDcc, setFilterDcc] = useState('')

  // Initialize filter state from initialData (once on mount, not on every conditions change)
  useEffect(() => {
    const cond = initialData?.conditions
    if (!cond) return
    setFilterFileRules(cond.fileRules?.map(r => r.pattern).join('\n') || '')
    setFilterSceneRules(cond.sceneRules?.map(r => r.pattern).join('\n') || '')
    
    if (cond.typeFilter) {
      const predefined = cond.typeFilter.types.filter(t => 
        cond.typeFilter?.dcc && DCC_TYPE_PRESETS[cond.typeFilter.dcc]?.includes(t)
      )
      const custom = cond.typeFilter.types.filter(t => 
        !cond.typeFilter?.dcc || !DCC_TYPE_PRESETS[cond.typeFilter.dcc]?.includes(t)
      )
      setFilterTypes(predefined)
      setFilterCustomTypes(custom.join('\n'))
      setFilterIsRegex(cond.typeFilter.isRegex || false)
      setFilterDcc(cond.typeFilter.dcc || '')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Run once on mount

  // Compute available events based on selected DCC
  const availableEvents = form.dcc ? (DCC_EVENTS[form.dcc] ?? []) : []

  // Notify parent whenever form changes (do NOT call onChange inside setForm updater).
  // Skip the very first render so that simply opening the editor doesn't mark dirty.
  const isFirstRender = useRef(true)
  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return }
    onChange?.(form)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form])

  const updateField = <K extends keyof TriggerFormData>(key: K, value: TriggerFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  /** Update multiple fields at once (avoids stale-closure issues with consecutive updateField calls) */
  const updateFields = (patch: Partial<TriggerFormData>) => {
    setForm((prev) => ({ ...prev, ...patch }))
  }

  const updateConditions = () => {
    const allTypes = [...filterTypes]
    if (filterCustomTypes.trim()) {
      allTypes.push(...filterCustomTypes.split('\n').filter(s => s.trim()).map(s => s.trim()))
    }
    
    const conditions: FilterConfig = {
      fileRules: filterFileRules.split('\n').filter(Boolean).map((p) => ({ pattern: p.trim() })),
      sceneRules: filterSceneRules.split('\n').filter(Boolean).map((p) => ({ pattern: p.trim(), isRegex: true })),
      typeFilter: allTypes.length > 0 ? { types: allTypes, dcc: filterDcc, isRegex: filterIsRegex } : undefined,
    }
    updateField('conditions', conditions)
  }

  // Update conditions when filter fields change
  useEffect(() => {
    updateConditions()
  }, [filterFileRules, filterSceneRules, filterTypes, filterCustomTypes, filterIsRegex, filterDcc])

  const addPresetRow = () => {
    setForm((prev) => ({
      ...prev,
      parameterPreset: [...prev.parameterPreset, { key: '', value: '' }],
    }))
  }

  const removePresetRow = (index: number) => {
    setForm((prev) => ({
      ...prev,
      parameterPreset: prev.parameterPreset.filter((_, i) => i !== index),
    }))
  }

  const updatePresetRow = (index: number, field: 'key' | 'value', val: string) => {
    setForm((prev) => ({
      ...prev,
      parameterPreset: prev.parameterPreset.map((row, i) =>
        i === index ? { ...row, [field]: val } : row,
      ),
    }))
  }

  const inputCls = 'w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small border border-border-default focus:border-accent focus:outline-none placeholder:text-text-dim transition-colors'

  return (
    <div className="bg-bg-secondary border border-border-default rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-body font-medium text-text-primary">
          {language === 'zh' ? '触发规则编辑器' : 'Trigger Rule Editor'}
        </h3>
        {onCancel && (
          <button onClick={onCancel} className="p-1 rounded hover:bg-bg-tertiary text-text-dim">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="space-y-4">
        {/* Name */}
        <FieldRow label={language === 'zh' ? '规则名称' : 'Rule Name'}>
          <input
            type="text"
            value={form.name}
            onChange={(e) => updateField('name', e.target.value)}
            placeholder={language === 'zh' ? '输入规则名称' : 'Enter rule name'}
            className={inputCls}
          />
        </FieldRow>

        {/* Trigger Type */}
        <FieldRow label={language === 'zh' ? '触发类型' : 'Trigger Type'}>
          <div className="flex gap-2 flex-wrap">
            {TRIGGER_TYPES.map((t) => (
              <button
                key={t.value}
                onClick={() => updateField('triggerType', t.value)}
                className={cn(
                  'px-3 py-1.5 rounded text-small transition-colors',
                  form.triggerType === t.value
                    ? 'bg-accent text-white'
                    : 'bg-bg-tertiary text-text-secondary hover:text-text-primary',
                )}
              >
                {language === 'zh' ? t.labelZh : t.labelEn}
              </button>
            ))}
          </div>
        </FieldRow>

        {/* Event-specific fields */}
        {form.triggerType === 'event' && (
          <>
            {/* DCC selector */}
            <FieldRow label={language === 'zh' ? 'DCC 软件' : 'DCC Software'}>
              <select
                value={form.dcc}
                onChange={(e) => updateFields({ dcc: e.target.value, eventType: '' })}
                className={inputCls}
              >
                <option value="">{language === 'zh' ? '选择 DCC' : 'Select DCC'}</option>
                {Object.keys(DCC_EVENTS).map((dccId) => (
                  <option key={dccId} value={dccId}>
                    {DCC_DISPLAY_NAMES[dccId] ?? dccId}
                  </option>
                ))}
              </select>
            </FieldRow>

            {/* Event type selector — event value already encodes timing (e.g. "asset.save.pre") */}
            {form.dcc && (
              <FieldRow label={language === 'zh' ? '事件类型' : 'Event Type'}>
                <select
                  value={form.eventType}
                  onChange={(e) => updateField('eventType', e.target.value)}
                  className={inputCls}
                >
                  <option value="">{language === 'zh' ? '选择事件类型' : 'Select event type'}</option>
                  {availableEvents.map((evt) => (
                    <option key={evt.event} value={evt.event}>
                      {language === 'zh' ? evt.label : evt.labelEn}
                    </option>
                  ))}
                </select>
              </FieldRow>
            )}
          </>
        )}

        {/* Schedule-specific fields */}
        {form.triggerType === 'schedule' && (
          <>
            <FieldRow label={language === 'zh' ? '调度类型' : 'Schedule Type'}>
              <div className="flex gap-2 flex-wrap">
                {SCHEDULE_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() =>
                      updateField('scheduleConfig', { ...form.scheduleConfig, type: t.value })
                    }
                    className={cn(
                      'px-3 py-1.5 rounded text-small transition-colors',
                      form.scheduleConfig.type === t.value
                        ? 'bg-accent text-white'
                        : 'bg-bg-tertiary text-text-secondary hover:text-text-primary',
                    )}
                  >
                    {language === 'zh' ? t.labelZh : t.labelEn}
                  </button>
                ))}
              </div>
            </FieldRow>

            {form.scheduleConfig.type === 'interval' && (
              <FieldRow label={language === 'zh' ? '执行间隔' : 'Interval'}>
                <input
                  type="text"
                  value={form.scheduleConfig.interval ?? ''}
                  onChange={(e) =>
                    updateField('scheduleConfig', { ...form.scheduleConfig, interval: e.target.value })
                  }
                  placeholder={language === 'zh' ? '例: 30m, 1h, 2h30m' : 'e.g. 30m, 1h, 2h30m'}
                  className={inputCls}
                />
              </FieldRow>
            )}

            {form.scheduleConfig.type === 'cron' && (
              <FieldRow label={language === 'zh' ? 'Cron 表达式' : 'Cron Expression'}>
                <input
                  type="text"
                  value={form.scheduleConfig.cron ?? ''}
                  onChange={(e) =>
                    updateField('scheduleConfig', { ...form.scheduleConfig, cron: e.target.value })
                  }
                  placeholder={language === 'zh' ? '例: 0 2 * * * (每天凌晨2点)' : 'e.g. 0 2 * * * (daily at 2am)'}
                  className={inputCls}
                />
              </FieldRow>
            )}

            {form.scheduleConfig.type === 'once' && (
              <FieldRow label={language === 'zh' ? '执行时间' : 'Run At'}>
                <input
                  type="datetime-local"
                  value={form.scheduleConfig.runAt ?? ''}
                  onChange={(e) =>
                    updateField('scheduleConfig', { ...form.scheduleConfig, runAt: e.target.value })
                  }
                  className={inputCls}
                />
              </FieldRow>
            )}
          </>
        )}

        {/* Watch-specific: no separate path input — uses filter conditions below */}
        {form.triggerType === 'watch' && (
          <div className="text-[11px] text-text-dim px-1 py-2 bg-bg-tertiary rounded border border-border-default">
            {language === 'zh'
              ? '💡 监听路径请在下方「筛选条件 → 文件筛选规则」中填写，支持 $variable 路径变量（如 $skills_installed/**/*.md）'
              : '💡 Set watch paths in "Filter Conditions → File filter rules" below. Supports $variable path variables.'}
          </div>
        )}

        {/* Execution Mode */}
        <FieldRow label={language === 'zh' ? '执行模式' : 'Execution Mode'}>
          <div className="flex gap-2 flex-wrap">
            {EXECUTION_MODES.map((m) => (
              <button
                key={m.value}
                title={language === 'zh' ? m.descZh : m.descEn}
                onClick={() => updateField('executionMode', m.value as ExecutionMode)}
                className={cn(
                  'px-3 py-1.5 rounded text-small transition-colors',
                  form.executionMode === m.value
                    ? 'bg-accent text-white'
                    : 'bg-bg-tertiary text-text-secondary hover:text-text-primary',
                )}
              >
                {language === 'zh' ? m.labelZh : m.labelEn}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-text-dim">
            {EXECUTION_MODES.find(m => m.value === form.executionMode)?.[language === 'zh' ? 'descZh' : 'descEn']}
          </p>
        </FieldRow>

        {/* Inline Filter Conditions — only for watch (file paths) and event (scene objects) */}
        {(form.triggerType === 'watch' || form.triggerType === 'event') && (
        <FieldRow label={language === 'zh' ? '筛选条件' : 'Filter Conditions'}>
          <div className="space-y-3 border rounded-lg p-3 bg-bg-tertiary">
            {/* Use default filters toggle (only show when tool has defaultFilters) */}
            {defaultFilters && (
              <div className="flex items-center gap-2 pb-2 border-b border-border-default/50">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.useDefaultFilters}
                    onChange={(e) => updateField('useDefaultFilters', e.target.checked)}
                    className="w-3.5 h-3.5 rounded border-border-default bg-bg-tertiary accent-accent"
                  />
                  <span className="text-small text-text-secondary">
                    {language === 'zh' ? '使用工具默认筛选条件' : 'Use tool default filters'}
                  </span>
                </label>
                {form.useDefaultFilters && defaultFilters.path && defaultFilters.path.length > 0 && (
                  <span className="text-[10px] text-text-dim ml-auto">
                    {defaultFilters.path.map(p => p.pattern).join(', ')}
                  </span>
                )}
              </div>
            )}

            {/* Custom filter fields — hidden when useDefaultFilters is on */}
            {!form.useDefaultFilters && (
              <>
                <div>
                  <label className="block text-[11px] text-text-dim mb-1.5">
                    {form.triggerType === 'watch'
                      ? (language === 'zh' ? '文件路径规则 (支持 $variable 和 glob)' : 'File path rules (supports $variable and glob)')
                      : (language === 'zh' ? '文件筛选规则 (gitignore 风格)' : 'File filter rules (gitignore style)')}
                  </label>
                  <PathRuleList
                    rules={filterFileRules.split('\n').filter(Boolean)}
                    onChange={(rules) => setFilterFileRules(rules.join('\n'))}
                    placeholder={form.triggerType === 'watch' ? '$project_root/tools/**/*' : '/Characters/**/*.fbx'}
                    inputCls={inputCls}
                    language={language}
                  />
                </div>
                
                {/* Scene object filter — only for event triggers (DCC scene context), not watch/schedule */}
                {(form.triggerType === 'event') && (
                  <div>
                    <label className="block text-[11px] text-text-dim mb-1">{language === 'zh' ? '场景对象筛选 (每行一条正则)' : 'Scene object filter (one regex per line)'}</label>
                    <textarea 
                      value={filterSceneRules} 
                      onChange={(e) => setFilterSceneRules(e.target.value)} 
                      rows={2} 
                      placeholder="^SM_.*" 
                      className={cn(inputCls, 'font-mono text-[11px] resize-y')} />
                  </div>
                )}
                
                {/* Object type filter — only for event triggers */}
                {(form.triggerType === 'event') && (
            <div>
              <label className="block text-[11px] text-text-dim mb-1">{language === 'zh' ? '对象类型筛选' : 'Object type filter'}</label>
              <div className="flex items-center gap-2 mb-2">
                <select 
                  value={filterDcc} 
                  onChange={(e) => { setFilterDcc(e.target.value); setFilterTypes([]) }} 
                  className={cn(inputCls, 'w-32')}>
                  <option value="">{language === 'zh' ? '选择DCC' : 'Select DCC'}</option>
                  {Object.keys(DCC_TYPE_PRESETS).map((d) => <option key={d} value={d}>{DCC_DISPLAY_NAMES[d] ?? d}</option>)}
                </select>
                <label className="flex items-center gap-1.5 text-[11px] text-text-secondary cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={filterIsRegex} 
                    onChange={(e) => setFilterIsRegex(e.target.checked)}
                    className="w-3 h-3 rounded border-border-default bg-bg-tertiary accent-accent" />
                  {language === 'zh' ? '正则匹配' : 'Regex match'}
                </label>
              </div>
              
              {filterDcc && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {(DCC_TYPE_PRESETS[filterDcc] ?? []).map((t) => (
                    <button 
                      key={t} 
                      onClick={() => setFilterTypes(filterTypes.includes(t) ? filterTypes.filter((x) => x !== t) : [...filterTypes, t])}
                      className={cn('text-[10px] px-2 py-0.5 rounded border transition-colors',
                        filterTypes.includes(t) ? 'bg-accent/20 text-accent border-accent/50' : 'bg-bg-tertiary text-text-dim border-border-default hover:text-text-secondary',
                      )}>
                      {t}
                    </button>
                  ))}
                </div>
              )}
              
              <div>
                <label className="block text-[11px] text-text-dim mb-1">{language === 'zh' ? '自定义类型规则 (每行一条)' : 'Custom type rules (one per line)'}</label>
                <textarea 
                  value={filterCustomTypes} 
                  onChange={(e) => setFilterCustomTypes(e.target.value)} 
                  rows={2} 
                  placeholder="BP_.*&#10;StaticMeshActor" 
                  className={cn(inputCls, 'font-mono text-[11px] resize-y')} />
              </div>
            </div>
            )}
              </>
            )}
            
            {/* Path variables help link */}
            <PathVariablesHelp language={language} />
          </div>
        </FieldRow>
        )}

        {/* Parameter Presets (inline key-value) */}
        <FieldRow label={language === 'zh' ? '参数预设' : 'Parameter Preset'}>
          <div className="space-y-2">
            {form.parameterPreset.map((row, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="text"
                  value={row.key}
                  onChange={(e) => updatePresetRow(i, 'key', e.target.value)}
                  placeholder={language === 'zh' ? '参数名' : 'Key'}
                  className={cn(inputCls, 'flex-1')}
                />
                <input
                  type="text"
                  value={row.value}
                  onChange={(e) => updatePresetRow(i, 'value', e.target.value)}
                  placeholder={language === 'zh' ? '值' : 'Value'}
                  className={cn(inputCls, 'flex-1')}
                />
                <button
                  onClick={() => removePresetRow(i)}
                  className="p-1.5 rounded text-error hover:bg-error/10 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
            <button
              onClick={addPresetRow}
              className="flex items-center gap-1 text-[12px] text-accent hover:text-accent-hover transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              {language === 'zh' ? '添加参数' : 'Add parameter'}
            </button>
          </div>
        </FieldRow>

        {/* Parameter Preset Reference */}
        {parameterPresets && parameterPresets.length > 0 && (
          <FieldRow label={language === 'zh' ? '参数预设引用' : 'Parameter Preset Reference'}>
            <select
              value={form.parameterPresetId}
              onChange={(e) => updateField('parameterPresetId', e.target.value)}
              className={inputCls}
            >
              <option value="">{language === 'zh' ? '不使用预设' : 'No preset'}</option>
              {parameterPresets.map((pp) => (
                <option key={pp.id} value={pp.id}>
                  {pp.name}
                </option>
              ))}
            </select>
          </FieldRow>
        )}

        {/* Enabled toggle */}
        <FieldRow label={language === 'zh' ? '启用状态' : 'Status'}>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.isEnabled}
              onChange={(e) => updateField('isEnabled', e.target.checked)}
              className="w-4 h-4 rounded border-border-default bg-bg-tertiary accent-accent"
            />
            <span className="text-small text-text-secondary">
              {form.isEnabled
                ? (language === 'zh' ? '已启用' : 'Enabled')
                : (language === 'zh' ? '已禁用' : 'Disabled')}
            </span>
          </label>
        </FieldRow>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 mt-6 pt-4 border-t border-border-default">
        <button
          onClick={() => onSave?.(form)}
          className="px-4 py-2 rounded bg-accent text-white text-small font-medium hover:bg-accent-hover transition-colors"
        >
          {language === 'zh' ? '保存规则' : 'Save Rule'}
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded bg-bg-tertiary text-text-secondary text-small hover:text-text-primary transition-colors"
          >
            {language === 'zh' ? '取消' : 'Cancel'}
          </button>
        )}
      </div>
    </div>
  )
}

// ---------- Path rule list (input list instead of textarea) ----------

function PathRuleList({
  rules,
  onChange,
  placeholder,
  inputCls,
  language,
}: {
  rules: string[]
  onChange: (rules: string[]) => void
  placeholder: string
  inputCls: string
  language: string
}) {
  const zh = language === 'zh'
  
  const updateRule = (index: number, value: string) => {
    const next = [...rules]
    next[index] = value
    onChange(next)
  }
  
  const removeRule = (index: number) => {
    onChange(rules.filter((_, i) => i !== index))
  }
  
  const addRule = () => {
    onChange([...rules, ''])
  }

  return (
    <div className="space-y-1.5">
      {rules.map((rule, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <input
            type="text"
            value={rule}
            onChange={(e) => updateRule(i, e.target.value)}
            placeholder={placeholder}
            className={cn(inputCls, 'flex-1 font-mono text-[11px]')}
          />
          <button
            onClick={() => removeRule(i)}
            className="p-1 rounded text-error/60 hover:text-error hover:bg-error/10 transition-colors shrink-0"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      ))}
      {rules.length === 0 && (
        <div className="text-[11px] text-text-dim py-1">
          {zh ? '暂无路径规则' : 'No path rules'}
        </div>
      )}
      <button
        onClick={addRule}
        className="flex items-center gap-1 text-[11px] text-accent hover:text-accent-hover transition-colors"
      >
        <Plus className="w-3 h-3" />
        {zh ? '添加路径规则' : 'Add path rule'}
      </button>
    </div>
  )
}

// ---------- Field row helper ----------

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-small text-text-secondary mb-1.5">{label}</label>
      {children}
    </div>
  )
}
