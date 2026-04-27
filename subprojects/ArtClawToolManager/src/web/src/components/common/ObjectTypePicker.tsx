// ObjectTypePicker: searchable multi-select combobox for DCC object types.
// Queries connected DCC for live types; falls back to static presets.
import { useState, useEffect, useRef, useCallback } from 'react'
import { X, ChevronDown, Loader2, Wifi, WifiOff } from 'lucide-react'
import { cn } from '../../utils/cn'
import { fetchDCCObjectTypes } from '../../api/client'
import type { DCCObjectType } from '../../api/client'

interface ObjectTypePickerProps {
  /** Currently selected type strings */
  value: string[]
  /** Callback when selection changes */
  onChange: (types: string[]) => void
  /** DCC identifier to query types for (e.g. "ue5", "maya2024") */
  dcc: string
  /** Placeholder text */
  placeholder?: string
  /** Language */
  language?: string
  /** Additional CSS class */
  className?: string
}

export default function ObjectTypePicker({
  value,
  onChange,
  dcc,
  placeholder,
  language = 'zh',
  className,
}: ObjectTypePickerProps) {
  const zh = language === 'zh'
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [types, setTypes] = useState<DCCObjectType[]>([])
  const [loading, setLoading] = useState(false)
  const [source, setSource] = useState<'live' | 'preset' | ''>('')

  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Fetch types when DCC changes or dropdown opens for the first time
  const loadTypes = useCallback(async () => {
    if (!dcc) return
    setLoading(true)
    try {
      const resp = await fetchDCCObjectTypes(dcc)
      if (resp.success && resp.data) {
        setTypes(resp.data.types || [])
        setSource(resp.data.source)
      }
    } catch {
      setTypes([])
      setSource('')
    }
    setLoading(false)
  }, [dcc])

  // Auto-fetch when DCC changes (eagerly, not just on open)
  useEffect(() => {
    setTypes([])
    setSource('')
    if (dcc) {
      loadTypes()
    }
  }, [dcc]) // eslint-disable-line react-hooks/exhaustive-deps

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Filter types by search
  const filtered = types.filter((t) =>
    t.type.toLowerCase().includes(search.toLowerCase()) ||
    t.label.toLowerCase().includes(search.toLowerCase())
  )

  // Separate selected vs unselected for display
  const selectedSet = new Set(value)

  const toggleType = (type: string) => {
    if (selectedSet.has(type)) {
      onChange(value.filter((v) => v !== type))
    } else {
      onChange([...value, type])
    }
  }

  const removeType = (type: string) => {
    onChange(value.filter((v) => v !== type))
  }

  // Handle manual input (Enter to add custom type)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && search.trim()) {
      e.preventDefault()
      const trimmed = search.trim()
      if (!selectedSet.has(trimmed)) {
        onChange([...value, trimmed])
      }
      setSearch('')
    }
    if (e.key === 'Escape') {
      setOpen(false)
    }
    if (e.key === 'Backspace' && !search && value.length > 0) {
      onChange(value.slice(0, -1))
    }
  }

  const inputCls = 'bg-transparent text-text-primary text-small outline-none placeholder:text-text-dim flex-1 min-w-[80px]'

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      {/* Input area with tags */}
      <div
        className={cn(
          'flex flex-wrap items-center gap-1 min-h-[36px] px-2.5 py-1.5 rounded border transition-colors cursor-text',
          'bg-bg-tertiary border-border-default',
          open && 'border-accent ring-1 ring-accent/20',
        )}
        onClick={() => { setOpen(true); inputRef.current?.focus() }}
      >
        {/* Selected tags */}
        {value.map((v) => (
          <span
            key={v}
            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-accent/15 text-accent text-[11px] font-mono"
          >
            {v}
            <button
              onClick={(e) => { e.stopPropagation(); removeType(v) }}
              className="hover:text-error transition-colors ml-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}

        {/* Search input */}
        <input
          ref={inputRef}
          value={search}
          onChange={(e) => { setSearch(e.target.value); if (!open) setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={value.length === 0 ? (placeholder ?? (zh ? '搜索或输入对象类型...' : 'Search or enter object type...')) : ''}
          className={inputCls}
        />

        {/* Indicators */}
        <div className="flex items-center gap-1 shrink-0 ml-auto">
          {loading && <Loader2 className="w-3.5 h-3.5 text-text-dim animate-spin" />}
          {!loading && source === 'live' && (
            <span title={zh ? 'DCC 实时数据' : 'Live from DCC'}>
              <Wifi className="w-3 h-3 text-success" />
            </span>
          )}
          {!loading && source === 'preset' && (
            <span title={zh ? '静态预设（DCC 未连接）' : 'Static presets (DCC not connected)'}>
              <WifiOff className="w-3 h-3 text-text-dim" />
            </span>
          )}
          <ChevronDown className={cn('w-3.5 h-3.5 text-text-dim transition-transform', open && 'rotate-180')} />
        </div>
      </div>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-[240px] overflow-y-auto rounded border border-border-default bg-bg-secondary shadow-lg">
          {/* Source indicator */}
          {source && (
            <div className="px-3 py-1.5 text-[10px] text-text-dim border-b border-border-default/50 flex items-center gap-1.5">
              {source === 'live' ? (
                <><Wifi className="w-3 h-3 text-success" /> {zh ? '来自 DCC 实时查询' : 'Live from DCC'}</>
              ) : (
                <><WifiOff className="w-3 h-3 text-text-dim" /> {zh ? '静态预设（DCC 未连接）' : 'Static presets (DCC not connected)'}</>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); loadTypes() }}
                className="ml-auto text-accent hover:text-accent-hover text-[10px]"
              >
                {zh ? '刷新' : 'Refresh'}
              </button>
            </div>
          )}

          {loading ? (
            <div className="px-3 py-4 text-center text-[11px] text-text-dim">
              <Loader2 className="w-4 h-4 animate-spin inline mr-1.5" />
              {zh ? '正在查询 DCC 对象类型...' : 'Querying DCC object types...'}
            </div>
          ) : filtered.length === 0 ? (
            <div className="px-3 py-3 text-[11px] text-text-dim text-center">
              {search ? (
                <>
                  {zh ? '未找到匹配类型，' : 'No match. '}
                  <span className="text-accent cursor-pointer" onClick={() => { if (search.trim()) { toggleType(search.trim()); setSearch('') } }}>
                    {zh ? `按 Enter 添加 "${search}"` : `Press Enter to add "${search}"`}
                  </span>
                </>
              ) : (
                <>{zh ? '暂无可用类型' : 'No types available'}</>
              )}
            </div>
          ) : (
            <div className="py-1">
              {filtered.map((t) => {
                const selected = selectedSet.has(t.type)
                return (
                  <button
                    key={t.type}
                    onClick={() => { toggleType(t.type); setSearch('') }}
                    className={cn(
                      'w-full text-left px-3 py-1.5 text-[12px] font-mono transition-colors flex items-center gap-2',
                      selected
                        ? 'bg-accent/10 text-accent'
                        : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary',
                    )}
                  >
                    <span className={cn(
                      'w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 text-[10px]',
                      selected ? 'border-accent bg-accent text-white' : 'border-border-default',
                    )}>
                      {selected && '✓'}
                    </span>
                    <span className="truncate">{t.label}</span>
                  </button>
                )
              })}
            </div>
          )}

          {/* Hint */}
          <div className="px-3 py-1.5 text-[10px] text-text-dim border-t border-border-default/50">
            {zh ? '输入自定义类型后按 Enter 添加' : 'Type custom name and press Enter to add'}
          </div>
        </div>
      )}
    </div>
  )
}
