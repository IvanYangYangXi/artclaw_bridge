// Ref: docs/ui/ui-design.md#StatusBar
// Status bar: connection, DCC, Agent, session, context usage, alerts
import { Circle, AlertTriangle, AlertCircle, X, Eye, EyeOff, Plus, Trash2 } from 'lucide-react'
import { cn } from '../../utils/cn'
import { useAppStore } from '../../stores/appStore'
import { useChatStore } from '../../stores/chatStore'
import { useState, useEffect } from 'react'
import { fetchAlerts, updateAlert, deleteAlert, getAlertStats } from '../../api/client'
import type { Alert, AlertStats } from '../../types'

const STATUS_TEXT: Record<string, Record<string, string>> = {
  zh: { connected: '已连接', disconnected: '已断开', connecting: '连接中' },
  en: { connected: 'Connected', disconnected: 'Disconnected', connecting: 'Connecting' },
}

const STATUS_COLOR: Record<string, string> = {
  connected: 'text-green-400',
  disconnected: 'text-gray-500',
  connecting: 'text-yellow-400',
}

export default function StatusBar() {
  const {
    currentDCC, dccOptions, setCurrentDCC,
    currentAgent, agents, currentPlatform,
    agentPlatforms, setCurrentPlatform, setCurrentAgent,
    language,
  } = useAppStore()
  const { connectionStatus, contextUsage, sessionEntries, activeSessionId, switchSession, createNewSession, deleteSessionEntry } = useChatStore()

  // Alert state
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [alertStats, setAlertStats] = useState<AlertStats | null>(null)
  const [showAlertModal, setShowAlertModal] = useState(false)
  const [showResolvedAlerts, setShowResolvedAlerts] = useState(false)
  const [isLoadingAlerts, setIsLoadingAlerts] = useState(false)

  // Load alerts
  const loadAlerts = async () => {
    try {
      setIsLoadingAlerts(true)
      const [alertResponse, stats] = await Promise.all([
        fetchAlerts(showResolvedAlerts ? undefined : false),
        getAlertStats()
      ])
      setAlerts(alertResponse.alerts)
      setAlertStats(stats)
    } catch (error) {
      console.error('Failed to load alerts:', error)
    } finally {
      setIsLoadingAlerts(false)
    }
  }

  // Poll alerts every 30 seconds
  useEffect(() => {
    loadAlerts()
    const interval = setInterval(loadAlerts, 30000)
    return () => clearInterval(interval)
  }, [showResolvedAlerts])

  // Resolve alert
  const handleResolveAlert = async (alertId: string) => {
    try {
      await updateAlert(alertId, { resolved: true })
      await loadAlerts()
    } catch (error) {
      console.error('Failed to resolve alert:', error)
    }
  }

  // Delete alert
  const handleDeleteAlert = async (alertId: string) => {
    try {
      await deleteAlert(alertId)
      await loadAlerts()
    } catch (error) {
      console.error('Failed to delete alert:', error)
    }
  }

  const t = STATUS_TEXT[language] ?? STATUS_TEXT.zh

  const platformAgents = agents.filter((a) => a.platform === currentPlatform)

  const usageColor =
    contextUsage.percentage > 80
      ? 'bg-red-500'
      : contextUsage.percentage > 60
        ? 'bg-yellow-500'
        : 'bg-green-500'

  // Alert indicator
  const unresolvedAlerts = alerts.filter(a => !a.resolvedAt)
  const hasErrors = unresolvedAlerts.some(a => a.level === 'error')
  const alertCount = unresolvedAlerts.length

  const selectClass = 'bg-gray-800 text-sm text-gray-200 border border-gray-600 rounded px-1.5 py-0.5 outline-none cursor-pointer hover:border-gray-400 transition-colors'

  return (
    <div className="shrink-0 border-b border-gray-700 bg-gray-800/80">
      <div className="flex items-center gap-3 px-4 h-10">
        {/* Connection status */}
        <div className={cn('flex items-center gap-1.5 text-xs', STATUS_COLOR[connectionStatus])}>
          <Circle className="w-2.5 h-2.5 fill-current" />
          <span>{t[connectionStatus]}</span>
          {connectionStatus === 'disconnected' && (
            <span className="text-gray-500 text-[10px] ml-1">
              {language === 'zh' ? '(本地模式)' : '(Local mode)'}
            </span>
          )}
        </div>

        {/* Alert indicator (always visible) */}
        <>
          <div className="w-px h-4 bg-gray-600" />
          <button
            onClick={() => setShowAlertModal(true)}
            className="flex items-center gap-1.5 text-xs hover:bg-gray-700 rounded px-1.5 py-0.5 transition-colors"
            title={alertCount > 0
              ? (language === 'zh' ? `${alertCount} 条未解决报警` : `${alertCount} unresolved alert(s)`)
              : (language === 'zh' ? '无报警' : 'No alerts')
            }
          >
            {alertCount > 0 ? (
              hasErrors ? (
                <AlertCircle className="w-3 h-3 text-red-400" />
              ) : (
                <AlertTriangle className="w-3 h-3 text-yellow-400" />
              )
            ) : (
              <AlertCircle className="w-3 h-3 text-gray-500" />
            )}
            {alertCount > 0 && (
              <span className={cn(
                'min-w-[16px] h-4 text-[10px] font-medium rounded-full flex items-center justify-center',
                hasErrors ? 'bg-red-500 text-white' : 'bg-yellow-500 text-black'
              )}>
                {alertCount}
              </span>
            )}
          </button>
        </>

        <div className="w-px h-4 bg-gray-600" />

        {/* DCC selector */}
        <select
          value={currentDCC}
          onChange={(e) => setCurrentDCC(e.target.value)}
          className={selectClass}
        >
          {dccOptions.map((d) => (
            <option key={d.id} value={d.id}>
              {d.icon} {d.name} {d.connected ? '●' : ''}
            </option>
          ))}
        </select>

        <div className="w-px h-4 bg-gray-600" />

        {/* Platform selector */}
        <select
          value={currentPlatform}
          onChange={(e) => setCurrentPlatform(e.target.value)}
          className={selectClass}
        >
          {agentPlatforms.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>

        {/* Agent selector */}
        {platformAgents.length > 0 && (
          <>
            <span className="text-gray-600 text-xs">/</span>
            <select
              value={currentAgent}
              onChange={(e) => setCurrentAgent(e.target.value)}
              className={selectClass}
            >
              {platformAgents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </>
        )}

        <div className="w-px h-4 bg-gray-600" />

        {/* Session selector + management */}
        <select
          value={activeSessionId}
          onChange={(e) => switchSession(e.target.value)}
          className={cn(selectClass, 'max-w-[150px] truncate')}
        >
          {sessionEntries.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
        {/* New session */}
        <button
          onClick={createNewSession}
          className="p-1 rounded text-gray-400 hover:text-gray-200 hover:bg-gray-700 transition-colors"
          title={language === 'zh' ? '新建会话' : 'New session'}
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
        {/* Delete current session (only if more than 1) */}
        {sessionEntries.length > 1 && (
          <button
            onClick={() => deleteSessionEntry(activeSessionId)}
            className="p-1 rounded text-gray-400 hover:text-red-400 hover:bg-gray-700 transition-colors"
            title={language === 'zh' ? '删除当前会话' : 'Delete session'}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}

        <div className="w-px h-4 bg-gray-600" />

        {/* Spacer */}
        <div className="flex-1" />

        {/* Context usage */}
        <div className="flex items-center gap-2" title={`${contextUsage.used.toLocaleString()} / ${contextUsage.total.toLocaleString()} tokens`}>
          <span className="text-[11px] text-gray-500">{language === 'zh' ? '上下文' : 'Context'}</span>
          <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={cn('h-full rounded-full transition-all', usageColor)}
              style={{ width: `${contextUsage.percentage}%` }}
            />
          </div>
          <span className="text-[11px] text-gray-500 w-8 text-right">{contextUsage.percentage}%</span>
        </div>
      </div>

      {/* Alert Modal */}
      {showAlertModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg shadow-xl w-[600px] max-h-[500px] overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <h3 className="text-lg font-semibold text-gray-200">
                {language === 'zh' ? '系统报警' : 'System Alerts'}
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowResolvedAlerts(!showResolvedAlerts)}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-300"
                >
                  {showResolvedAlerts ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  {showResolvedAlerts 
                    ? (language === 'zh' ? '隐藏已解决' : 'Hide Resolved')
                    : (language === 'zh' ? '显示已解决' : 'Show Resolved')
                  }
                </button>
                <button
                  onClick={() => setShowAlertModal(false)}
                  className="text-gray-400 hover:text-gray-300"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="max-h-[400px] overflow-y-auto">
              {isLoadingAlerts ? (
                <div className="p-8 text-center text-gray-400">
                  {language === 'zh' ? '加载中...' : 'Loading...'}
                </div>
              ) : alerts.length === 0 ? (
                <div className="p-8 text-center text-gray-400">
                  {language === 'zh' ? '暂无报警' : 'No alerts'}
                </div>
              ) : (
                <div className="p-4 space-y-3">
                  {alerts.map((alert) => (
                    <div key={alert.id} className={cn(
                      'p-3 rounded-lg border',
                      alert.resolvedAt ? 'bg-gray-900 border-gray-600 opacity-60' : 'bg-gray-850 border-gray-600',
                      alert.level === 'error' ? 'border-l-4 border-l-red-500' : 'border-l-4 border-l-yellow-500'
                    )}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            {alert.level === 'error' ? (
                              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                            ) : (
                              <AlertTriangle className="w-4 h-4 text-yellow-400 shrink-0" />
                            )}
                            <h4 className="text-sm font-medium text-gray-200 truncate">
                              {alert.title}
                            </h4>
                            {alert.resolvedAt && (
                              <span className="text-xs text-green-400">
                                {language === 'zh' ? '已解决' : 'Resolved'}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-400 mb-2 leading-relaxed">
                            {alert.detail}
                          </p>
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-gray-500">
                              {language === 'zh' ? '来源' : 'Source'}: {alert.source}
                            </span>
                            <span className="text-xs text-gray-500">
                              {new Date(alert.createdAt).toLocaleString()}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          {!alert.resolvedAt && (
                            <button
                              onClick={() => handleResolveAlert(alert.id)}
                              className="text-xs px-2 py-1 bg-green-600 hover:bg-green-700 text-white rounded"
                            >
                              {language === 'zh' ? '解决' : 'Resolve'}
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteAlert(alert.id)}
                            className="text-xs px-2 py-1 bg-gray-600 hover:bg-gray-700 text-gray-300 rounded"
                          >
                            {language === 'zh' ? '删除' : 'Delete'}
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            {alertStats && (
              <div className="p-4 border-t border-gray-700 bg-gray-900 text-xs text-gray-400">
                <div className="flex justify-between">
                  <span>
                    {language === 'zh' 
                      ? `总计: ${alertStats.total} | 未解决: ${alertStats.unresolved}`
                      : `Total: ${alertStats.total} | Unresolved: ${alertStats.unresolved}`
                    }
                  </span>
                  <span>
                    {language === 'zh'
                      ? `错误: ${alertStats.errors} | 警告: ${alertStats.warnings}`
                      : `Errors: ${alertStats.errors} | Warnings: ${alertStats.warnings}`
                    }
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
