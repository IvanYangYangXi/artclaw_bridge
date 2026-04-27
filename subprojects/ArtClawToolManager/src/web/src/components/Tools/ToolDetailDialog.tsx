// Ref: docs/ui/ui-design.md#Tools
// Tool detail drawer: single-page sections with unified save
// Sections: Info, Parameter Presets, Trigger Rules
import { useState, useEffect, useCallback } from 'react'
import {
  X, Plus, Trash2, Star, Save, Copy, Package, Code, Layers, Pencil,
} from 'lucide-react'
import { cn } from '../../utils/cn'
import { useAppStore } from '../../stores/appStore'
import { DCC_DISPLAY_NAMES, getEventLabel } from '../../constants/dccTypes'
import type {
  ToolItemExtended, ParameterPreset, TriggerRuleData, ImplementationType, ToolParameter,
} from '../../types'
import TriggerRuleEditor, { type TriggerFormData } from './TriggerRuleEditor'
import PathVariablesHelp from '../common/PathVariablesHelp'
import {
  fetchPresets, fetchTriggers,
  createTrigger, deleteTrigger, updateTrigger, updateTool, createTool,
} from '../../api/client'
import { useToolsStore } from '../../stores/toolsStore'

// ---------- Props ----------

interface ToolDetailDialogProps {
  tool: ToolItemExtended
  open: boolean
  onClose: () => void
  onPresetsChange?: () => void
}

// ---------- Constants ----------

const IMPL_ICONS: Record<ImplementationType, React.ReactNode> = {
  skill_wrapper: <Package className="w-3.5 h-3.5" />,
  script: <Code className="w-3.5 h-3.5" />,
  composite: <Layers className="w-3.5 h-3.5" />,
}

// ---------- Component ----------

export default function ToolDetailDialog({ tool, open, onClose, onPresetsChange }: ToolDetailDialogProps) {
  const language = useAppStore((s) => s.language)
  const zh = language === 'zh'

  // -- Editable state (all changes buffered until save) --
  const [name, setName] = useState(tool.name)
  const [description, setDescription] = useState(tool.description ?? '')
  const [author, setAuthor] = useState(tool.author ?? '')
  const [presets, setPresets] = useState<ParameterPreset[]>([])
  const [triggers, setTriggers] = useState<TriggerRuleData[]>([])

  // UI state
  const [activePresetId, setActivePresetId] = useState<string | null>(null)
  const [showNewPreset, setShowNewPreset] = useState(false)
  const [showNewTrigger, setShowNewTrigger] = useState(false)
  const [editingTriggerId, setEditingTriggerId] = useState<string | null>(null)
  const [pendingTriggerForm, setPendingTriggerForm] = useState<import('./TriggerRuleEditor').TriggerFormData | null>(null)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [pendingDefaultFilters, setPendingDefaultFilters] = useState<import('../../types').FilterConfig | null>(null)

  // New preset form
  const [newPresetName, setNewPresetName] = useState('')
  const [newPresetDesc, setNewPresetDesc] = useState('')
  const [newPresetValues, setNewPresetValues] = useState<Record<string, string>>({})

  // Editable inputs (script parameters)
  const [editedInputs, setEditedInputs] = useState<ToolParameter[] | null>(null)

  const inputs: ToolParameter[] = editedInputs ?? (tool.manifest?.inputs as ToolParameter[]) ?? []

  // -- Load data --
  useEffect(() => {
    if (!open) return
    setName(tool.name)
    setDescription(tool.description ?? '')
    setAuthor(tool.author ?? '')
    setEditedInputs(null)
    setDirty(false)
    // Load presets
    fetchPresets(tool.id).then((r) => { if (r.success) setPresets((r.data ?? []) as ParameterPreset[]) }).catch(() => {})
    // Load triggers
    fetchTriggers(tool.id).then((r) => { if (r.success) setTriggers((r.data ?? []) as TriggerRuleData[]) }).catch(() => {})
  }, [open, tool.id, tool.name, tool.description])

  const markDirty = useCallback(() => setDirty(true), [])

  // -- Save --
  const handleSave = async () => {
    setSaving(true)
    try {
      // Save pending trigger edit if any
      if (editingTriggerId && pendingTriggerForm) {
        await handleUpdateTrigger(editingTriggerId, pendingTriggerForm)
        setPendingTriggerForm(null)
      }
      // Only send the sub-fields that the user can actually edit in this dialog.
      // Never spread the full tool.manifest — it may be stale/incomplete and would overwrite
      // fields on disk that are not exposed in the UI (triggers, outputs, implementation, etc.)
      const manifestPatch: Record<string, unknown> = {
        inputs: editedInputs ?? tool.manifest?.inputs,
        presets,
        defaultFilters: pendingDefaultFilters ?? tool.manifest?.defaultFilters,
      }
      const resp = await updateTool(tool.id, { name, description, author, manifest: manifestPatch })
      setDirty(false)
      // Sync local state from API response so reopening the panel shows updated values
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const saved = (resp as any)?.data
      if (saved) {
        if (saved.name != null) setName(saved.name)
        if (saved.author != null) setAuthor(saved.author)
        if (saved.description != null) setDescription(saved.description)
      }
      // Refresh tool list so ToolCard also reflects the latest data (triggers sync_manifest too)
      await useToolsStore.getState().fetchToolsList()
      // Re-fetch triggers: if name changed, orphan rules were cleaned up by sync_manifest
      const tr = await fetchTriggers(tool.id)
      if (tr.success) setTriggers((tr.data ?? []) as TriggerRuleData[])
      onPresetsChange?.()
    } catch (e) { console.error('[handleSave] error:', e) }
    setSaving(false)
  }

  const handleSaveAsNew = async () => {
    setSaving(true)
    try {
      const newManifest = { ...(tool.manifest ?? {}), name: `${name} (copy)`, inputs: editedInputs ?? tool.manifest?.inputs, presets }
      await createTool({ name: `${name} (copy)`, description, source: 'user', target_dccs: tool.targetDCCs, implementation_type: tool.implementationType ?? 'script', manifest: newManifest })
      onPresetsChange?.()
      onClose()
    } catch { /* ignore */ }
    setSaving(false)
  }

  // -- Preset CRUD (local state) --
  const handleCreatePreset = () => {
    const id = `preset-${Date.now()}`
    const now = new Date().toISOString()
    const values: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(newPresetValues)) { if (v) values[k] = v }
    setPresets((prev) => [...prev, { id, name: newPresetName || 'New Preset', description: newPresetDesc, isDefault: false, values, createdAt: now, updatedAt: now }])
    setNewPresetName(''); setNewPresetDesc(''); setNewPresetValues({}); setShowNewPreset(false)
    markDirty()
  }

  const handleDeletePreset = (id: string) => {
    setPresets((prev) => prev.filter((p) => p.id !== id))
    if (activePresetId === id) setActivePresetId(null)
    markDirty()
  }

  const handleSetDefault = (id: string) => {
    setPresets((prev) => prev.map((p) => ({ ...p, isDefault: p.id === id })))
    markDirty()
  }

  const handlePresetValueChange = (presetId: string, key: string, value: string) => {
    setPresets((prev) => prev.map((p) => p.id === presetId ? { ...p, values: { ...p.values, [key]: value }, updatedAt: new Date().toISOString() } : p))
    markDirty()
  }

  const handlePresetFieldChange = (presetId: string, field: 'name' | 'description', value: string) => {
    setPresets((prev) => prev.map((p) => p.id === presetId ? { ...p, [field]: value } : p))
    markDirty()
  }

  /** Convert editor conditions to API format.
   *  For watch triggers, map fileRules → conditions.path (manifest filters format). */
  const conditionsToApi = (data: TriggerFormData): Record<string, unknown> => {
    const cond: Record<string, unknown> = {}
    if (data.triggerType === 'watch') {
      // Watch triggers use filters.path format
      if (data.conditions.fileRules?.length) {
        cond.path = data.conditions.fileRules.map((r) => ({ pattern: r.pattern }))
      }
      if (data.conditions.sceneRules?.length) {
        cond.name = data.conditions.sceneRules.map((r) => ({ pattern: r.pattern }))
      }
    } else {
      // Event/manual triggers use legacy format
      if (data.conditions.fileRules?.length) cond.fileRules = data.conditions.fileRules
      if (data.conditions.sceneRules?.length) cond.sceneRules = data.conditions.sceneRules
    }
    if (data.conditions.typeFilter) cond.typeFilter = data.conditions.typeFilter
    return cond
  }

  // -- Trigger CRUD (API calls) --
  const handleCreateTrigger = async (data: TriggerFormData) => {
    try {
      const resp = await createTrigger(tool.id, {
        name: data.name, trigger_type: data.triggerType, dcc: data.dcc, event_type: data.eventType,
        execution_mode: data.executionMode, is_enabled: data.isEnabled,
        conditions: conditionsToApi(data), parameter_preset_id: data.parameterPresetId,
        schedule_config: data.scheduleConfig,
      })
      if (resp.success && resp.data) setTriggers((prev) => [...prev, resp.data as TriggerRuleData])
    } catch { /* ignore */ }
    setShowNewTrigger(false)
  }

  const handleDeleteTrigger = async (id: string) => {
    try { await deleteTrigger(id); setTriggers((prev) => prev.filter((t) => t.id !== id)) } catch { /* ignore */ }
    if (editingTriggerId === id) setEditingTriggerId(null)
  }

  const handleUpdateTrigger = async (id: string, data: TriggerFormData) => {
    try {
      const resp = await updateTrigger(id, {
        name: data.name, trigger_type: data.triggerType, dcc: data.dcc, event_type: data.eventType,
        execution_mode: data.executionMode, is_enabled: data.isEnabled,
        conditions: conditionsToApi(data), parameter_preset_id: data.parameterPresetId,
        schedule_config: data.scheduleConfig,
      })
      if (resp.success && resp.data) {
        // snakeToCamel the response
        const updated = Object.fromEntries(
          Object.entries(resp.data as Record<string, unknown>).map(([k, v]) => [k.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase()), v])
        ) as unknown as TriggerRuleData
        setTriggers((prev) => prev.map((t) => t.id === id ? updated : t))
      }
    } catch { /* ignore */ }
    setEditingTriggerId(null)
  }

  const handleToggleTrigger = async (id: string, currentEnabled: boolean) => {
    try {
      const resp = await updateTrigger(id, { is_enabled: !currentEnabled })
      if (resp.success) {
        setTriggers((prev) => prev.map((t) => t.id === id ? { ...t, isEnabled: !currentEnabled } : t))
      }
    } catch { /* ignore */ }
  }

  /** Convert TriggerRuleData → TriggerFormData for the editor.
   *  Maps both new format (conditions.path/name) and legacy (conditions.fileRules/sceneRules). */
  const triggerToFormData = (t: TriggerRuleData): TriggerFormData => {
    const cond = t.conditions || {}

    // Map conditions.path → fileRules (manifest filters format → editor format)
    let fileRules: Array<{ pattern: string }> = cond.fileRules || []
    if (!fileRules.length && Array.isArray(cond.path)) {
      fileRules = cond.path.map((p: { pattern: string }) => ({ pattern: p.pattern }))
    }

    let sceneRules: Array<{ pattern: string }> = cond.sceneRules || []
    if (!sceneRules.length && Array.isArray(cond.name)) {
      sceneRules = cond.name.map((n: { pattern: string }) => ({ pattern: n.pattern }))
    }

    return {
      name: t.name || '',
      triggerType: (t.triggerType || 'manual') as TriggerFormData['triggerType'],
      dcc: t.dcc || '',
      eventType: t.eventType || '',
      executionMode: (t.executionMode || 'notify') as TriggerFormData['executionMode'],
      useDefaultFilters: (t as TriggerRuleData & { useDefaultFilters?: boolean; use_default_filters?: boolean }).useDefaultFilters
        ?? (t as TriggerRuleData & { use_default_filters?: boolean }).use_default_filters
        ?? false,
      conditions: {
        fileRules,
        sceneRules,
        typeFilter: cond.typeFilter,
      },
      parameterPreset: [],
      parameterPresetId: (t as TriggerRuleData & { parameterPresetId?: string }).parameterPresetId || '',
      isEnabled: t.isEnabled ?? true,
      scheduleConfig: (t.scheduleConfig as TriggerFormData['scheduleConfig']) || { type: 'interval' },
    }
  }

  if (!open) return null

  const inputCls = 'w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small border border-border-default focus:border-accent focus:outline-none placeholder:text-text-dim transition-colors'

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-[40%] min-w-[380px] max-w-[600px] bg-bg-primary border-l border-border-default z-50 flex flex-col animate-slide-in-right">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-5 py-4 border-b border-border-default">
          <h2 className="text-body font-semibold text-text-primary">{zh ? '工具详情' : 'Tool Details'}</h2>
          <div className="flex items-center gap-2">
            {dirty && (
              <span className="text-[10px] text-warning px-1.5 py-0.5 rounded bg-warning/10">{zh ? '未保存' : 'Unsaved'}</span>
            )}
            <button onClick={onClose} className="p-1.5 rounded hover:bg-bg-tertiary text-text-dim"><X className="w-4 h-4" /></button>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">

          {/* ── Section 1: Basic Info ── */}
          <Section title={zh ? '📋 基本信息' : '📋 Basic Info'}>
            <label className="block text-[11px] text-text-dim mb-1">{zh ? '名称' : 'Name'}</label>
            <input value={name} onChange={(e) => { setName(e.target.value); markDirty() }} className={inputCls} />
            <label className="block text-[11px] text-text-dim mb-1 mt-3">{zh ? '描述' : 'Description'}</label>
            <textarea value={description} onChange={(e) => { setDescription(e.target.value); markDirty() }} rows={2} className={cn(inputCls, 'resize-y')} />
            <label className="block text-[11px] text-text-dim mb-1 mt-3">{zh ? '作者' : 'Author'}</label>
            <input value={author} onChange={(e) => { setAuthor(e.target.value); markDirty() }} placeholder={zh ? '作者名称' : 'Author name'} className={inputCls} />
            <div className="flex items-center gap-4 mt-3 text-[11px] text-text-dim flex-wrap">
              <span>{zh ? '版本' : 'Version'}: {tool.version ?? '0.0.0'}</span>
              <span>{zh ? '来源' : 'Source'}: {tool.source}</span>
              <span className="flex items-center gap-1">{IMPL_ICONS[tool.implementationType ?? 'script']} {tool.implementationType ?? 'script'}</span>
              {tool.targetDCCs && tool.targetDCCs.length > 0 && <span>DCC: {tool.targetDCCs.map((d) => DCC_DISPLAY_NAMES[d] ?? d).join(', ')}</span>}
            </div>
            <div className="flex items-center gap-4 mt-2 text-[11px] text-text-dim flex-wrap">
              {tool.createdAt && <span>{zh ? '创建' : 'Created'}: {tool.createdAt.slice(0, 10)}</span>}
              {tool.updatedAt && <span>{zh ? '更新' : 'Updated'}: {tool.updatedAt.slice(0, 10)}</span>}
            </div>
          </Section>

          {/* ── Section 1.5: Script Parameters (editable) ── */}
          {inputs.length > 0 && (
            <Section title={zh ? '📦 脚本参数' : '📦 Script Parameters'}>
              <p className="text-[10px] text-text-dim mb-2">{zh ? '可编辑参数名、默认值和描述，保存后写入 manifest.json' : 'Edit name, default value and description. Saved to manifest.json'}</p>
              <div className="space-y-2">
                {inputs.map((input, i) => (
                  <div key={input.id} className="flex items-start gap-2 p-2 rounded bg-bg-tertiary border border-border-default/50">
                    <div className="flex-1 min-w-0 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <input
                          value={input.name}
                          onChange={(e) => {
                            const updated = [...inputs]
                            updated[i] = { ...updated[i], name: e.target.value }
                            markDirty()
                            // Update manifest inputs in local state — will be saved on handleSave
                            setEditedInputs(updated)
                          }}
                          className={cn(inputCls, 'flex-1 text-[12px] font-mono')}
                          placeholder={zh ? '参数名' : 'Param name'}
                        />
                        <span className="px-1.5 py-0.5 bg-bg-quaternary rounded text-[10px] text-text-dim shrink-0">{input.type}</span>
                        <label className="flex items-center gap-1 text-[10px] text-text-dim shrink-0 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={input.required}
                            onChange={(e) => {
                              const updated = [...inputs]
                              updated[i] = { ...updated[i], required: e.target.checked }
                              markDirty()
                              setEditedInputs(updated)
                            }}
                            className="w-3 h-3 rounded accent-accent"
                          />
                          {zh ? '必填' : 'Req'}
                        </label>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-text-dim w-12 shrink-0">{zh ? '默认值' : 'Default'}</span>
                        <input
                          value={input.default !== undefined ? String(input.default) : ''}
                          onChange={(e) => {
                            const updated = [...inputs]
                            const raw = e.target.value
                            let parsed: unknown = raw
                            if (input.type === 'number' && raw !== '') parsed = Number(raw)
                            else if (input.type === 'boolean') parsed = raw === 'true'
                            else if (raw === '') parsed = undefined
                            updated[i] = { ...updated[i], default: parsed }
                            markDirty()
                            setEditedInputs(updated)
                          }}
                          placeholder={zh ? '无默认值' : 'No default'}
                          className={cn(inputCls, 'flex-1 text-[11px] font-mono')}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-text-dim w-12 shrink-0">{zh ? '描述' : 'Desc'}</span>
                        <input
                          value={input.description ?? ''}
                          onChange={(e) => {
                            const updated = [...inputs]
                            updated[i] = { ...updated[i], description: e.target.value || undefined }
                            markDirty()
                            setEditedInputs(updated)
                          }}
                          placeholder={zh ? '参数说明' : 'Description'}
                          className={cn(inputCls, 'flex-1 text-[11px]')}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* ── Section 2: Parameter Presets ── */}
          <Section title={zh ? '⭐ 参数预设' : '⭐ Parameter Presets'}>
            {/* Tag list */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {presets.map((p) => (
                <button key={p.id} onClick={() => setActivePresetId(activePresetId === p.id ? null : p.id)}
                  className={cn('text-[11px] px-2.5 py-1 rounded border transition-colors',
                    activePresetId === p.id ? 'bg-accent/20 text-accent border-accent/50' : 'bg-bg-tertiary text-text-secondary border-border-default hover:bg-bg-quaternary',
                  )}>
                  {p.isDefault && '★ '}{p.name}
                </button>
              ))}
              <button onClick={() => { setShowNewPreset(!showNewPreset); setActivePresetId(null) }}
                className="text-[11px] px-2 py-1 rounded border border-dashed border-border-default text-text-dim hover:text-accent hover:border-accent transition-colors">
                <Plus className="w-3 h-3 inline -mt-0.5" /> {zh ? '新建' : 'New'}
              </button>
            </div>

            {/* New preset form */}
            {showNewPreset && (
              <div className="border border-border-default rounded-lg p-3 mb-3 bg-bg-secondary space-y-2">
                <input value={newPresetName} onChange={(e) => setNewPresetName(e.target.value)} placeholder={zh ? '预设名称' : 'Preset name'} className={inputCls} />
                <input value={newPresetDesc} onChange={(e) => setNewPresetDesc(e.target.value)} placeholder={zh ? '描述 (可选)' : 'Description (optional)'} className={inputCls} />
                {inputs.map((inp) => (
                  <div key={inp.id} className="flex items-center gap-2">
                    <span className="text-[11px] text-text-dim w-24 shrink-0 truncate">{inp.name}</span>
                    <input value={newPresetValues[inp.id] ?? ''} onChange={(e) => setNewPresetValues((v) => ({ ...v, [inp.id]: e.target.value }))}
                      placeholder={String(inp.default ?? '')} className={cn(inputCls, 'flex-1')} />
                  </div>
                ))}
                <div className="flex gap-2 pt-1">
                  <button onClick={handleCreatePreset} className="px-3 py-1.5 rounded text-[11px] bg-accent text-white hover:bg-accent/90">{zh ? '创建' : 'Create'}</button>
                  <button onClick={() => setShowNewPreset(false)} className="px-3 py-1.5 rounded text-[11px] text-text-dim hover:bg-bg-tertiary">{zh ? '取消' : 'Cancel'}</button>
                </div>
              </div>
            )}

            {/* Active preset editor */}
            {activePresetId && (() => {
              const preset = presets.find((p) => p.id === activePresetId)
              if (!preset) return null
              return (
                <div className="border border-accent/30 rounded-lg p-3 bg-accent/5 space-y-2">
                  <div className="flex items-center gap-2">
                    <input value={preset.name} onChange={(e) => handlePresetFieldChange(preset.id, 'name', e.target.value)}
                      className={cn(inputCls, 'flex-1 text-[12px]')} />
                    <button onClick={() => handleSetDefault(preset.id)} title={zh ? '设为默认' : 'Set default'}
                      className={cn('p-1.5 rounded transition-colors', preset.isDefault ? 'text-accent' : 'text-text-dim hover:text-accent')}>
                      <Star className="w-3.5 h-3.5" fill={preset.isDefault ? 'currentColor' : 'none'} />
                    </button>
                    <button onClick={() => handleDeletePreset(preset.id)} className="p-1.5 rounded text-text-dim hover:text-error transition-colors">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <input value={preset.description ?? ''} onChange={(e) => handlePresetFieldChange(preset.id, 'description', e.target.value)}
                    placeholder={zh ? '描述' : 'Description'} className={cn(inputCls, 'text-[11px]')} />
                  {inputs.map((inp) => (
                    <div key={inp.id} className="flex items-center gap-2">
                      <span className="text-[11px] text-text-dim w-24 shrink-0 truncate">{inp.name}</span>
                      <input value={String(preset.values[inp.id] ?? '')}
                        onChange={(e) => handlePresetValueChange(preset.id, inp.id, e.target.value)}
                        placeholder={String(inp.default ?? '')} className={cn(inputCls, 'flex-1 text-[12px]')} />
                    </div>
                  ))}
                </div>
              )
            })()}

            {presets.length === 0 && !showNewPreset && (
              <p className="text-[11px] text-text-dim">{zh ? '暂无预设' : 'No presets yet'}</p>
            )}
          </Section>

          {/* ── Section 3.5: Default Filters ── */}
          <Section title={zh ? '🔍 默认筛选条件' : '🔍 Default Filters'}>
            <p className="text-[11px] text-text-dim mb-2">
              {zh
                ? '工具级默认筛选条件，触发规则可选择继承此条件或自定义覆盖。脚本可统一读取此配置。'
                : 'Tool-level default filter conditions. Trigger rules can inherit or override. Scripts read this as the canonical source.'}
            </p>
            <DefaultFiltersEditor
              filters={pendingDefaultFilters ?? tool.manifest?.defaultFilters}
              onSave={async (filters) => {
                setPendingDefaultFilters(filters)
                markDirty()
              }}
              language={language}
            />
          </Section>

          {/* ── Section 4: Trigger Rules ── */}
          <Section title={zh ? '⚡ 触发规则' : '⚡ Trigger Rules'}>
            {triggers.length > 0 ? (
              <div className="space-y-2 mb-3">
                {triggers.map((t) => {
                  const tAny = t as TriggerRuleData & { parameterPresetId?: string; trigger_type?: string }
                  const triggerType = tAny.trigger_type || (t.dcc ? 'event' : 'manual')
                  const dccLabel = t.dcc ? (DCC_DISPLAY_NAMES[t.dcc] ?? t.dcc) : ''
                  const eventLabel = t.dcc && t.eventType ? getEventLabel(t.dcc, t.eventType, language) : t.eventType
                  const ppName = tAny.parameterPresetId ? presets.find((p) => p.id === tAny.parameterPresetId)?.name : undefined
                  const hasInlineFilter = t.conditions && (
                    t.conditions.fileRules?.length ||
                    t.conditions.sceneRules?.length ||
                    t.conditions.typeFilter ||
                    t.conditions.path?.length
                  )
                  const triggerTypeLabels: Record<string, string> = zh
                    ? { manual: '手动', event: '事件', schedule: '定时', watch: '监听' }
                    : { manual: 'Manual', event: 'Event', schedule: 'Schedule', watch: 'Watch' }
                  const typeLabel = triggerTypeLabels[triggerType] ?? triggerType
                  return (
                    <div key={t.id}>
                      <div className="flex items-start gap-2 p-2.5 rounded border border-border-default bg-bg-secondary hover:border-accent/30 transition-colors">
                        {/* Enable/disable toggle */}
                        <button
                          onClick={() => handleToggleTrigger(t.id, t.isEnabled ?? true)}
                          title={t.isEnabled ? (zh ? '点击禁用' : 'Click to disable') : (zh ? '点击启用' : 'Click to enable')}
                          className="mt-1 shrink-0"
                        >
                          <span className={cn('block w-2.5 h-2.5 rounded-full transition-colors', t.isEnabled !== false ? 'bg-success hover:bg-success/60' : 'bg-text-dim hover:bg-text-dim/60')} />
                        </button>
                        {/* Clickable content area */}
                        <div
                          className="flex-1 min-w-0 cursor-pointer"
                          onClick={() => setEditingTriggerId(editingTriggerId === t.id ? null : t.id)}
                        >
                          <div className="text-small text-text-primary truncate">{t.name || (zh ? '未命名' : 'Unnamed')}</div>
                          <div className="text-[11px] text-text-dim mt-0.5 flex items-center gap-1.5 flex-wrap">
                            <span className="px-1.5 py-0.5 rounded bg-bg-quaternary text-[10px]">{typeLabel}</span>
                            {dccLabel && <span>{dccLabel}</span>}
                            {eventLabel && <span>{eventLabel}</span>}
                            <span>{t.executionMode}</span>
                          </div>
                          {(hasInlineFilter || ppName) && (
                            <div className="text-[10px] text-text-dim mt-0.5">
                              {hasInlineFilter && <span className="mr-3">🔍 {zh ? '内联筛选' : 'Inline filter'}</span>}
                              {ppName && <span>⭐ {ppName}</span>}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-0.5 shrink-0">
                          <button onClick={() => setEditingTriggerId(editingTriggerId === t.id ? null : t.id)} className="p-1 rounded text-text-dim hover:text-accent transition-colors">
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => handleDeleteTrigger(t.id)} className="p-1 rounded text-text-dim hover:text-error transition-colors">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      {/* Inline editor when expanded */}
                      {editingTriggerId === t.id && (
                        <div className="mt-2 mb-1">
                          <TriggerRuleEditor
                            initialData={triggerToFormData(t)}
                            parameterPresets={presets.map((p) => ({ id: p.id, name: p.name }))}
                            defaultFilters={tool.manifest?.defaultFilters}
                            onSave={(data) => handleUpdateTrigger(t.id, data)}
                            onChange={(data) => setPendingTriggerForm(data)}
                            onCancel={() => { setEditingTriggerId(null); setPendingTriggerForm(null) }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-[11px] text-text-dim mb-3">{zh ? '暂无触发规则' : 'No trigger rules yet'}</p>
            )}

            {showNewTrigger ? (
              <TriggerRuleEditor
                parameterPresets={presets.map((p) => ({ id: p.id, name: p.name }))}
                defaultFilters={tool.manifest?.defaultFilters}
                onSave={handleCreateTrigger}
                onCancel={() => setShowNewTrigger(false)}
              />
            ) : !editingTriggerId && (
              <button onClick={() => { setShowNewTrigger(true); setEditingTriggerId(null) }}
                className="flex items-center gap-1 text-[12px] text-accent hover:text-accent-hover transition-colors">
                <Plus className="w-3.5 h-3.5" />{zh ? '添加规则' : 'Add Rule'}
              </button>
            )}
          </Section>
        </div>

        {/* Footer */}
        <div className="shrink-0 flex items-center justify-end gap-3 px-5 py-4 border-t border-border-default">
          <button onClick={onClose} className="px-4 py-2 rounded text-small text-text-secondary hover:bg-bg-tertiary transition-colors">
            {zh ? '取消' : 'Cancel'}
          </button>
          <button onClick={handleSaveAsNew} disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 rounded text-small text-text-secondary hover:bg-bg-tertiary border border-border-default transition-colors disabled:opacity-50">
            <Copy className="w-3.5 h-3.5" />{zh ? '另存为新工具' : 'Save As New Tool'}
          </button>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 rounded text-small font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-50 transition-colors">
            <Save className="w-3.5 h-3.5" />{zh ? '保存' : 'Save'}
          </button>
        </div>
      </div>
    </>
  )
}

// ---------- Default Filters Editor ----------

function DefaultFiltersEditor({
  filters,
  onSave,
  language,
}: {
  filters?: import('../../types').FilterConfig
  onSave: (filters: import('../../types').FilterConfig) => Promise<void>
  language: string
}) {
  const zh = language === 'zh'
  const [pathRules, setPathRules] = useState<string[]>(() =>
    (filters?.path || []).map(p => p.pattern)
  )
  const [typeInput, setTypeInput] = useState<string>(
    () => (filters?.typeFilter?.types || []).join(', ')
  )

  const inputCls = 'w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small border border-border-default focus:border-accent focus:outline-none placeholder:text-text-dim transition-colors'

  // 每次变化立即上报给父级（父级统一在右下角保存）
  const notify = (newPaths: string[], newTypeInput: string) => {
    const pathEntries = newPaths.filter(r => r.trim()).map(pattern => ({ pattern: pattern.trim() }))
    const types = newTypeInput.split(',').map(s => s.trim()).filter(Boolean)
    onSave({
      ...filters,
      path: pathEntries,
      typeFilter: types.length ? { types } : undefined,
    })
  }

  const updatePath = (index: number, value: string) => {
    const next = [...pathRules]; next[index] = value; setPathRules(next); notify(next, typeInput)
  }
  const removePath = (index: number) => {
    const next = pathRules.filter((_, i) => i !== index); setPathRules(next); notify(next, typeInput)
  }
  const addPath = () => {
    const next = [...pathRules, '']; setPathRules(next); notify(next, typeInput)
  }
  const updateTypeInput = (value: string) => {
    setTypeInput(value); notify(pathRules, value)
  }

  return (
    <div className="space-y-4">
      {/* 对象类型筛选 */}
      <div className="space-y-1.5">
        <label className="block text-[11px] text-text-dim">
          {zh ? '对象类型 (逗号分隔，如 StaticMesh, SkeletalMesh)' : 'Object types (comma-separated, e.g. StaticMesh, SkeletalMesh)'}
        </label>
        <input
          type="text"
          value={typeInput}
          onChange={(e) => updateTypeInput(e.target.value)}
          placeholder="StaticMesh, SkeletalMesh"
          className={cn(inputCls, 'font-mono text-[11px]')}
        />
      </div>

      {/* 路径规则 */}
      <div className="space-y-1.5">
        <label className="block text-[11px] text-text-dim">
          {zh ? '路径规则 (支持 $variable 和 glob)' : 'Path rules (supports $variable and glob)'}
        </label>
        {pathRules.map((rule, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <input
              type="text"
              value={rule}
              onChange={(e) => updatePath(i, e.target.value)}
              placeholder="/Game/MyContent/**/*"
              className={cn(inputCls, 'flex-1 font-mono text-[11px]')}
            />
            <button
              onClick={() => removePath(i)}
              className="p-1 rounded text-error/60 hover:text-error hover:bg-error/10 transition-colors shrink-0"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        ))}
        {pathRules.length === 0 && (
          <div className="text-[11px] text-text-dim py-1">
            {zh ? '暂无路径规则（匹配全部路径）' : 'No path rules (match all paths)'}
          </div>
        )}
        <div className="flex items-center gap-3">
          <button
            onClick={addPath}
            className="flex items-center gap-1 text-[11px] text-accent hover:text-accent-hover transition-colors"
          >
            <Plus className="w-3 h-3" />
            {zh ? '添加路径规则' : 'Add path rule'}
          </button>
        </div>
        <PathVariablesHelp language={language} />
      </div>
    </div>
  )
}

// ---------- Section wrapper ----------

function Section({ title, children, headerRight }: { title: string; children: React.ReactNode; headerRight?: React.ReactNode }) {
  return (
    <div className="px-5 py-4 border-b border-border-default">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-small font-medium text-text-primary">{title}</h3>
        {headerRight}
      </div>
      {children}
    </div>
  )
}
