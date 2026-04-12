// Ref: docs/features/phase5-dcc-integration.md
// DCC connection status panel for Settings page and Sidebar
import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Wifi, WifiOff } from 'lucide-react'
import { cn } from '../../utils/cn'
import { fetchDCCStatus, refreshDCCStatus } from '../../api/client'
import type { DCCStatusInfo } from '../../types'

// DCC display configuration
const DCC_DISPLAY: Record<string, { name: string; icon: string }> = {
  ue57: { name: 'Unreal Engine', icon: '🎮' },
  maya2024: { name: 'Maya', icon: '🗿' },
  max2024: { name: '3ds Max', icon: '📐' },
  blender: { name: 'Blender', icon: '🧊' },
  comfyui: { name: 'ComfyUI', icon: '🎨' },
  sp: { name: 'Substance Painter', icon: '🖌️' },
  sd: { name: 'Stable Diffusion', icon: '🖼️' },
  houdini: { name: 'Houdini', icon: '🌪️' },
}

function formatTime(ts: number): string {
  if (!ts) return 'Never'
  const d = new Date(ts * 1000)
  const now = Date.now()
  const diffMs = now - d.getTime()
  if (diffMs < 60000) return 'Just now'
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`
  return d.toLocaleTimeString()
}

interface DCCStatusPanelProps {
  compact?: boolean
}

export default function DCCStatusPanel({ compact = false }: DCCStatusPanelProps) {
  const [statuses, setStatuses] = useState<Record<string, DCCStatusInfo>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchDCCStatus()
      if (res.success && res.data) {
        setStatuses(res.data)
      }
    } catch {
      setError('Failed to load DCC status')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleRefresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await refreshDCCStatus()
      if (res.success && res.data) {
        setStatuses(res.data)
      }
    } catch {
      setError('Failed to refresh')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  const entries = Object.entries(statuses)
  const connectedCount = entries.filter(([, s]) => s.connected).length

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-[11px] text-text-dim px-1">
        <span className={cn(connectedCount > 0 ? 'text-success' : 'text-text-dim')}>
          {connectedCount > 0 ? <Wifi className="w-3 h-3 inline" /> : <WifiOff className="w-3 h-3 inline" />}
        </span>
        <span>DCC: {connectedCount}/{entries.length}</span>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border-default bg-bg-secondary p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary">DCC Connections</h3>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className={cn(
            'p-1.5 rounded text-text-dim hover:text-text-primary hover:bg-bg-tertiary transition-colors',
            loading && 'animate-spin'
          )}
          title="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {error && (
        <p className="text-xs text-error mb-2">{error}</p>
      )}

      {/* Status list */}
      <div className="space-y-2">
        {entries.map(([key, status]) => {
          const display = DCC_DISPLAY[key] || { name: key, icon: '🔧' }
          return (
            <div
              key={key}
              className="flex items-center justify-between py-1.5 px-2 rounded bg-bg-primary"
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'w-2 h-2 rounded-full',
                    status.connected ? 'bg-success' : 'bg-text-dim'
                  )}
                />
                <span className="text-xs">{display.icon}</span>
                <span className="text-xs text-text-primary">{display.name}</span>
              </div>
              <span className="text-[10px] text-text-dim">
                {status.connected ? 'Connected' : formatTime(status.last_check)}
              </span>
            </div>
          )
        })}
      </div>

      {entries.length === 0 && !loading && (
        <p className="text-xs text-text-dim text-center py-4">No DCC adapters configured</p>
      )}
    </div>
  )
}
