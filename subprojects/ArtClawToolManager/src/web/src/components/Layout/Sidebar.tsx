// Ref: docs/ui/ui-design.md#Sidebar
// Sidebar navigation: pages, DCC selector, Agent selector, language toggle
import { useLocation, useNavigate } from 'react-router-dom'
import {
  MessageSquare,
  Package,
  LayoutList,
  Wrench,
  Settings,
  ChevronLeft,
  ChevronRight,
  Globe,
  Circle,
} from 'lucide-react'
import { cn } from '../../utils/cn'
import { useAppStore } from '../../stores/appStore'
import type { PageKey } from '../../types'

interface NavEntry {
  key: PageKey
  label: string
  labelEn: string
  icon: React.ReactNode
  path: string
}

const NAV_ITEMS: NavEntry[] = [
  { key: 'chat', label: '对话', labelEn: 'Chat', icon: <MessageSquare className="w-4 h-4" />, path: '/' },
  { key: 'skills', label: 'Skills', labelEn: 'Skills', icon: <Package className="w-4 h-4" />, path: '/skills' },
  { key: 'workflows', label: 'Workflows', labelEn: 'Workflows', icon: <LayoutList className="w-4 h-4" />, path: '/workflows' },
  { key: 'tools', label: '工具', labelEn: 'Tools', icon: <Wrench className="w-4 h-4" />, path: '/tools' },
  { key: 'settings', label: '设置', labelEn: 'Settings', icon: <Settings className="w-4 h-4" />, path: '/settings' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const {
    sidebarCollapsed,
    toggleSidebar,
    language,
    setLanguage,
    dccOptions,
    currentDCC,
    setCurrentDCC,
    agentPlatforms,
    currentPlatform,
    setCurrentPlatform,
    agents,
    currentAgent,
    setCurrentAgent,
  } = useAppStore()

  const platformAgents = agents.filter((a) => a.platform === currentPlatform)

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  const selectClass = 'w-full px-2 py-1.5 rounded text-xs bg-gray-800 text-gray-200 border border-gray-600 focus:border-blue-500 focus:outline-none'

  return (
    <aside
      className={cn(
        'flex flex-col h-full bg-gray-900 border-r border-gray-700 transition-all duration-200',
        sidebarCollapsed ? 'w-12' : 'w-[200px]',
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-12 border-b border-gray-700 shrink-0">
        {!sidebarCollapsed && (
          <span className="text-sm font-semibold text-blue-400 truncate">ArtClaw</span>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1 rounded hover:bg-gray-700 text-gray-500 hover:text-gray-200 transition-colors"
        >
          {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 px-1.5 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            onClick={() => navigate(item.path)}
            className={cn(
              'w-full flex items-center gap-2.5 px-2.5 py-2 rounded text-sm transition-colors',
              isActive(item.path)
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200',
            )}
            title={sidebarCollapsed ? (language === 'zh' ? item.label : item.labelEn) : undefined}
          >
            {item.icon}
            {!sidebarCollapsed && (
              <span className="truncate">{language === 'zh' ? item.label : item.labelEn}</span>
            )}
          </button>
        ))}
      </nav>

      {/* Bottom controls */}
      {!sidebarCollapsed && (
        <div className="px-2 py-2 border-t border-gray-700 space-y-2 shrink-0">
          {/* DCC Selector with connection indicators */}
          <div>
            <label className="block text-[11px] text-gray-500 mb-1 px-1">DCC</label>
            <select
              value={currentDCC}
              onChange={(e) => setCurrentDCC(e.target.value)}
              className={selectClass}
            >
              {dccOptions.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.icon} {d.name} {d.connected ? '🟢' : ''}
                </option>
              ))}
            </select>
            {/* Connection indicator for selected DCC */}
            {(() => {
              const selected = dccOptions.find((d) => d.id === currentDCC)
              if (!selected) return null
              return (
                <div className="flex items-center gap-1.5 mt-1 px-1">
                  <Circle className={cn('w-2 h-2 fill-current', selected.connected ? 'text-green-400' : 'text-gray-600')} />
                  <span className="text-[10px] text-gray-500">
                    {selected.connected
                      ? (language === 'zh' ? '已连接' : 'Connected')
                      : (language === 'zh' ? '未连接' : 'Not connected')}
                  </span>
                </div>
              )
            })()}
          </div>

          {/* Agent Platform */}
          <div>
            <label className="block text-[11px] text-gray-500 mb-1 px-1">
              {language === 'zh' ? 'Agent 平台' : 'Platform'}
            </label>
            <div className="space-y-0.5">
              {agentPlatforms.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setCurrentPlatform(p.id)}
                  className={cn(
                    'w-full flex items-center justify-between px-2 py-1.5 rounded text-xs transition-colors',
                    currentPlatform === p.id
                      ? 'bg-blue-500/20 text-blue-400'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200',
                  )}
                >
                  <span className="truncate">{p.name}</span>
                  <span className={cn('text-[10px]', p.configured ? 'text-green-400' : 'text-gray-600')}>
                    {p.configured ? '●' : '○'}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Agent */}
          <div>
            <label className="block text-[11px] text-gray-500 mb-1 px-1">Agent</label>
            <select
              value={currentAgent}
              onChange={(e) => setCurrentAgent(e.target.value)}
              className={selectClass}
            >
              {platformAgents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>

          {/* Language toggle */}
          <button
            onClick={() => setLanguage(language === 'zh' ? 'en' : 'zh')}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
          >
            <Globe className="w-3.5 h-3.5" />
            <span>{language === 'zh' ? '中 / EN' : 'EN / 中'}</span>
          </button>
        </div>
      )}
    </aside>
  )
}
