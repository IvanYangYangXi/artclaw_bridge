// Ref: docs/features/phase5-dcc-integration.md
// Settings page with General, Connection, and Advanced tabs
import { useState, useEffect, useCallback } from 'react'
import { Globe, Server, Zap, RefreshCw, ExternalLink, Moon, Wifi, WifiOff, Save } from 'lucide-react'
import TabBar from '../../components/common/TabBar'
import DCCStatusPanel from '../../components/Layout/DCCStatusPanel'
import { useAppStore } from '../../stores/appStore'
import { fetchTriggerStats, fetchPlatformsConfig, updatePlatformGateway, detectPlatformPort } from '../../api/client'
import type { TriggerEngineStats } from '../../types'

type SettingsTab = 'general' | 'connection' | 'advanced'

const TABS: { key: SettingsTab; label: string }[] = [
  { key: 'general', label: '通用' },
  { key: 'connection', label: '连接' },
  { key: 'advanced', label: '高级' },
]

// --- General Settings Tab ---
function GeneralSettings() {
  const { language, setLanguage } = useAppStore()
  const [sendMode, setSendMode] = useState<'enter' | 'ctrl-enter'>('enter')

  return (
    <div className="space-y-6">
      {/* Language */}
      <SettingSection title="Language / 语言" icon={<Globe className="w-4 h-4" />}>
        <div className="flex gap-2">
          <OptionButton
            label="中文"
            active={language === 'zh'}
            onClick={() => setLanguage('zh')}
          />
          <OptionButton
            label="English"
            active={language === 'en'}
            onClick={() => setLanguage('en')}
          />
        </div>
      </SettingSection>

      {/* Theme */}
      <SettingSection title="Theme / 主题" icon={<Moon className="w-4 h-4" />}>
        <div className="flex gap-2">
          <OptionButton label="Dark" active={true} onClick={() => {}} />
          <OptionButton label="Light" active={false} onClick={() => {}} disabled />
        </div>
        <p className="text-[11px] text-text-dim mt-1">Light theme coming soon</p>
      </SettingSection>

      {/* Send mode */}
      <SettingSection title="Send Mode / 发送方式">
        <div className="flex gap-2">
          <OptionButton
            label="Enter"
            active={sendMode === 'enter'}
            onClick={() => setSendMode('enter')}
          />
          <OptionButton
            label="Ctrl+Enter"
            active={sendMode === 'ctrl-enter'}
            onClick={() => setSendMode('ctrl-enter')}
          />
        </div>
      </SettingSection>
    </div>
  )
}

// --- Connection Settings Tab ---
interface PlatformState {
  type: string
  name: string
  currentUrl: string
  editUrl: string
  isDetecting: boolean
  isSaving: boolean
  connected: boolean
}

function ConnectionSettings() {
  const [gatewayUrl, setGatewayUrl] = useState('ws://localhost:9876')
  const [triggerStats, setTriggerStats] = useState<TriggerEngineStats | null>(null)
  const [platforms, setPlatforms] = useState<PlatformState[]>([])

  const loadTriggerStats = useCallback(async () => {
    try {
      const res = await fetchTriggerStats()
      if (res.success && res.data) {
        setTriggerStats(res.data)
      }
    } catch {
      // ignore
    }
  }, [])

  const loadPlatforms = useCallback(async () => {
    try {
      const res = await fetchPlatformsConfig()
      if (res.success && res.data) {
        setPlatforms(
          res.data.map((p) => ({
            type: p.type,
            name: p.name,
            currentUrl: p.gateway_url,
            editUrl: p.gateway_url,
            isDetecting: false,
            isSaving: false,
            connected: true,
          })),
        )
      }
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    loadTriggerStats()
    loadPlatforms()
  }, [loadTriggerStats, loadPlatforms])

  const handleSavePlatform = useCallback(async (platform: PlatformState) => {
    setPlatforms((prev) =>
      prev.map((p) => (p.type === platform.type ? { ...p, isSaving: true } : p)),
    )
    try {
      await updatePlatformGateway(platform.type, platform.editUrl)
      setPlatforms((prev) =>
        prev.map((p) =>
          p.type === platform.type
            ? { ...p, currentUrl: p.editUrl, isSaving: false }
            : p,
        ),
      )
    } catch {
      setPlatforms((prev) =>
        prev.map((p) => (p.type === platform.type ? { ...p, isSaving: false } : p)),
      )
    }
  }, [])

  const handleDetectPlatform = useCallback(async (platform: PlatformState) => {
    setPlatforms((prev) =>
      prev.map((p) => (p.type === platform.type ? { ...p, isDetecting: true } : p)),
    )
    try {
      const res = await detectPlatformPort(platform.type)
      if (res.success && res.data) {
        setPlatforms((prev) =>
          prev.map((p) =>
            p.type === platform.type
              ? { ...p, editUrl: res.data!.url, isDetecting: false }
              : p,
          ),
        )
      } else {
        setPlatforms((prev) =>
          prev.map((p) =>
            p.type === platform.type ? { ...p, isDetecting: false } : p,
          ),
        )
      }
    } catch {
      setPlatforms((prev) =>
        prev.map((p) =>
          p.type === platform.type ? { ...p, isDetecting: false } : p,
        ),
      )
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Gateway URL */}
      <SettingSection title="Gateway URL" icon={<Server className="w-4 h-4" />}>
        <div className="flex gap-2">
          <input
            type="text"
            value={gatewayUrl}
            onChange={(e) => setGatewayUrl(e.target.value)}
            className="flex-1 px-3 py-1.5 rounded text-sm bg-bg-tertiary text-text-primary border border-border-default focus:border-accent focus:outline-none"
          />
          <button className="px-3 py-1.5 rounded text-sm bg-accent text-white hover:bg-accent/80 transition-colors">
            Save
          </button>
        </div>
      </SettingSection>

      {/* Platform Gateways */}
      <SettingSection title="Platform Gateways" icon={<Server className="w-4 h-4" />}>
        <div className="space-y-3">
          {platforms.map((platform) => (
            <div
              key={platform.type}
              className="rounded-lg border border-border-default bg-bg-secondary p-4 space-y-3"
            >
              {/* Platform header row */}
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-text-secondary" />
                <span className="text-sm font-medium text-text-primary">{platform.name}</span>
                {/* Connection status */}
                <span className="flex items-center gap-1 ml-auto">
                  {platform.connected ? (
                    <>
                      <Wifi className="w-3.5 h-3.5 text-success" />
                      <span className="text-xs text-success">Connected</span>
                    </>
                  ) : (
                    <>
                      <WifiOff className="w-3.5 h-3.5 text-text-dim" />
                      <span className="text-xs text-text-dim">Disconnected</span>
                    </>
                  )}
                </span>
              </div>

              {/* Gateway URL row */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-secondary shrink-0">Gateway:</span>
                <input
                  type="text"
                  value={platform.editUrl}
                  onChange={(e) =>
                    setPlatforms((prev) =>
                      prev.map((p) =>
                        p.type === platform.type
                          ? { ...p, editUrl: e.target.value }
                          : p,
                      ),
                    )
                  }
                  className="flex-1 px-3 py-1.5 rounded text-sm bg-bg-tertiary text-text-primary border border-border-default focus:border-accent focus:outline-none"
                  placeholder="ws://127.0.0.1:18789"
                />
                <button
                  onClick={() => handleDetectPlatform(platform)}
                  disabled={platform.isDetecting}
                  className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-bg-tertiary text-text-secondary border border-border-default hover:bg-bg-tertiary/70 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <RefreshCw
                    className={`w-3 h-3 ${platform.isDetecting ? 'animate-spin' : ''}`}
                  />
                  Auto Detect
                </button>
                <button
                  onClick={() => handleSavePlatform(platform)}
                  disabled={platform.isSaving || platform.editUrl === platform.currentUrl}
                  className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-accent text-white hover:bg-accent/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Save className="w-3 h-3" />
                  Save
                </button>
              </div>

              {/* Current saved URL indicator */}
              {platform.editUrl !== platform.currentUrl && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-text-dim">Saved:</span>
                  <code className="text-[11px] text-text-secondary bg-bg-tertiary px-1.5 py-0.5 rounded">
                    {platform.currentUrl}
                  </code>
                </div>
              )}
            </div>
          ))}
        </div>
      </SettingSection>

      {/* DCC Status */}
      <SettingSection title="DCC Connections" icon={<Zap className="w-4 h-4" />}>
        <DCCStatusPanel />
      </SettingSection>

      {/* Trigger Engine */}
      <SettingSection title="Trigger Engine" icon={<Zap className="w-4 h-4" />}>
        <div className="rounded-lg border border-border-default bg-bg-secondary p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-secondary">Status</span>
            <span className={`text-xs font-medium ${triggerStats?.running ? 'text-success' : 'text-text-dim'}`}>
              {triggerStats?.running ? 'Running' : 'Stopped'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-secondary">Total Rules</span>
            <span className="text-xs text-text-primary">{triggerStats?.total_rules ?? 0}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-secondary">Event Rules</span>
            <span className="text-xs text-text-primary">{triggerStats?.event_rules ?? 0}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-secondary">Scheduled Jobs</span>
            <span className="text-xs text-text-primary">{triggerStats?.scheduled_jobs ?? 0}</span>
          </div>
          <button
            onClick={loadTriggerStats}
            className="w-full mt-2 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-xs text-text-secondary hover:bg-bg-tertiary transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
      </SettingSection>
    </div>
  )
}

// --- Advanced Settings Tab ---
function AdvancedSettings() {
  return (
    <div className="space-y-6">
      <SettingSection title="API Documentation">
        <a
          href="/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
        >
          Open API Docs <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </SettingSection>

      <SettingSection title="Data">
        <p className="text-xs text-text-dim">Database and cache management options coming soon.</p>
      </SettingSection>
    </div>
  )
}

// --- Shared Components ---
function SettingSection({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary mb-2">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  )
}

function OptionButton({ label, active, onClick, disabled }: { label: string; active: boolean; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`px-3 py-1.5 rounded text-xs transition-colors ${
        active
          ? 'bg-accent/20 text-accent border border-accent/40'
          : 'bg-bg-tertiary text-text-secondary border border-border-default hover:border-border-hover'
      } ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
    >
      {label}
    </button>
  )
}

// --- Main Page ---
export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')

  return (
    <div className="flex flex-col h-full bg-bg-primary">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-border-default bg-bg-secondary">
        <h1 className="text-title text-text-primary mb-3">Settings</h1>
        <TabBar tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 max-w-2xl">
        {activeTab === 'general' && <GeneralSettings />}
        {activeTab === 'connection' && <ConnectionSettings />}
        {activeTab === 'advanced' && <AdvancedSettings />}
      </div>
    </div>
  )
}
