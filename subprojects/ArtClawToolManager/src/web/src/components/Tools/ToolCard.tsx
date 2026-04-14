// Ref: docs/ui/ui-design.md#Tools
// Tool card: name, description, version, source, implementation type, status, action buttons
import {
  Star,
  Download,
  Play,
  Trash2,
  Edit,
  Zap,
  Package,
  Code,
  Layers,
  FolderOpen,
  Plus,
  Upload,
  Info,
} from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { cn } from '../../utils/cn'
import type { ToolItemExtended } from '../../types'
import { useToolsStore } from '../../stores/toolsStore'
import PublishDialog, { type PublishData } from '../common/PublishDialog'
import ToolDetailDialog from './ToolDetailDialog'

interface ToolCardProps {
  tool: ToolItemExtended
  onRun?: (tool: ToolItemExtended, params?: Record<string, unknown>) => void
  onEdit?: (tool: ToolItemExtended) => void
}

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  installed: { label: '已安装', color: 'bg-success/20 text-success' },
  not_installed: { label: '可安装', color: 'bg-bg-tertiary text-text-dim' },
  update_available: { label: '有更新', color: 'bg-warning/20 text-warning' },
}

const SOURCE_LABEL: Record<string, string> = {
  official: '官方',
  marketplace: '市集',
  user: '我的',
}

const IMPL_BADGE: Record<string, { label: string; icon: React.ReactNode }> = {
  skill_wrapper: { label: '包装', icon: <Package className="w-3 h-3" /> },
  script: { label: '脚本', icon: <Code className="w-3 h-3" /> },
  composite: { label: '组合', icon: <Layers className="w-3 h-3" /> },
}

export default function ToolCard({ tool, onRun, onEdit }: ToolCardProps) {
  const {
    selectedToolIds,
    toggleSelectTool,
    doFavorite,
    doUnfavorite,
    doDelete,
  } = useToolsStore()

  const [_showDirDropdown, _setShowDirDropdown] = useState(false)
  const [showPublish, setShowPublish] = useState(false)
  const [showDetail, setShowDetail] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const isSelected = selectedToolIds.has(tool.id)
  const badge = STATUS_BADGE[tool.status]
  const isFavorited = tool.runtimeStatus?.favorited ?? false
  const implBadge = tool.implementationType ? IMPL_BADGE[tool.implementationType] : null

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        _setShowDirDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleRunWithPreset = (preset: any) => {
    onRun?.(tool, preset.values)
  }

  const handleAddPreset = () => {
    alert('添加预设功能即将推出')
  }

  const handleOpenDirectory = async () => {
    _setShowDirDropdown(false)
    try {
      await fetch(`/api/v1/tools/${tool.id}/open-dir`, {
        method: 'POST',
      })
    } catch (error) {
      console.error('Failed to open directory:', error)
    }
  }

  const handlePublish = async (data: PublishData) => {
    try {
      await fetch(`/api/v1/tools/${tool.id}/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      // 刷新 tools 列表
      useToolsStore.getState().fetchToolsList()
    } catch (error) {
      console.error('Failed to publish tool:', error)
      throw error
    }
  }

  return (
    <>
    <div
      className={cn(
        'group relative rounded-lg border p-4 transition-colors',
        isSelected
          ? 'border-accent bg-accent/5'
          : 'border-border-default bg-bg-secondary hover:border-border-hover',
      )}
    >
      {/* Checkbox (visible on hover / when selected) */}
      <div
        className={cn(
          'absolute top-3 left-3 transition-opacity',
          isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
        )}
      >
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => toggleSelectTool(tool.id)}
          className="w-4 h-4 rounded border-border-default bg-bg-tertiary accent-accent cursor-pointer"
        />
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0 pl-6 group-hover:pl-6">
          <span className="text-body font-medium text-text-primary truncate">{tool.name}</span>
          {implBadge && (
            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-bg-tertiary text-text-dim shrink-0">
              {implBadge.icon}
              {implBadge.label}
            </span>
          )}
        </div>
        <span className={cn('shrink-0 text-[11px] px-2 py-0.5 rounded-full', badge.color)}>
          {badge.label}
        </span>
      </div>

      {/* Description */}
      <p className="text-small text-text-secondary mb-3 line-clamp-2 pl-6">{tool.description}</p>

      {/* Meta */}
      <div className="flex items-center gap-2 text-[11px] text-text-dim mb-3 pl-6 flex-wrap">
        <span>{SOURCE_LABEL[tool.source]}</span>
        <span>·</span>
        <span>v{tool.version ?? '0.0.0'}</span>
        {tool.author && (
          <>
            <span>·</span>
            <span>{tool.author}</span>
          </>
        )}
        {tool.updatedAt && (
          <>
            <span>·</span>
            <span>{tool.updatedAt.slice(0, 10)}</span>
          </>
        )}
        {tool.targetDCCs.length > 0 && (
          <>
            <span>·</span>
            <span className="text-blue-400">{tool.targetDCCs.join(', ')}</span>
          </>
        )}
        {tool.stats.rating > 0 && (
          <>
            <span>·</span>
            <span className="flex items-center gap-0.5">
              <Star className="w-3 h-3 fill-warning text-warning" />
              {tool.stats.rating}
            </span>
          </>
        )}
        {tool.stats.downloads > 0 && (
          <>
            <span>·</span>
            <span className="flex items-center gap-0.5">
              <Download className="w-3 h-3" />
              {tool.stats.downloads >= 1000
                ? `${(tool.stats.downloads / 1000).toFixed(1)}k`
                : tool.stats.downloads}
            </span>
          </>
        )}
        {(tool.triggerCount ?? 0) > 0 && (
          <>
            <span>·</span>
            <span className="flex items-center gap-0.5">
              <Zap className="w-3 h-3 text-warning" />
              {tool.triggerCount} 触发规则
            </span>
            <span>·</span>
            <span className="flex items-center gap-0.5">
              ⚡ {(() => {
                const triggers = tool.manifest?.triggers
                if (!triggers || triggers.length === 0) return '手动'
                const triggerTypes = [...new Set(triggers.map((t: any) => t.type || t.triggerType || 'manual'))]
                const typeLabels: Record<string, string> = {
                  manual: '手动',
                  event: '事件',
                  schedule: '定时',
                  watch: '监控'
                }
                return triggerTypes.map(type => typeLabels[type] || type).join(' / ')
              })()}
            </span>
          </>
        )}
      </div>

      {/* Parameter Presets */}
      {tool.presets && tool.presets.length > 0 && (
        <div className="flex items-center gap-2 mb-3 pl-6 flex-wrap">
          <span className="text-[10px] text-text-dim">预设:</span>
          {tool.presets.slice(0, 3).map((preset) => (
            <button
              key={preset.id}
              onClick={() => handleRunWithPreset(preset)}
              className={cn(
                'text-[10px] px-2 py-0.5 rounded border cursor-pointer hover:bg-gray-700 transition-colors',
                preset.isDefault
                  ? 'bg-blue-500/20 text-blue-400 border-blue-500'
                  : 'bg-gray-800 text-gray-300 border-gray-600'
              )}
              title={preset.description}
            >
              {preset.isDefault && '[默认] '}
              {preset.name}
            </button>
          ))}
          {tool.presets.length > 3 && (
            <span className="text-[10px] px-2 py-0.5 rounded border bg-gray-800 text-gray-300 border-gray-600 cursor-pointer hover:bg-gray-700">
              +{tool.presets.length - 3}
            </span>
          )}
          <button
            onClick={handleAddPreset}
            className="text-[10px] px-2 py-0.5 rounded border bg-gray-700 text-gray-400 border-gray-600 cursor-pointer hover:bg-gray-600 transition-colors flex items-center gap-1"
            title="添加新预设"
          >
            <Plus className="w-2.5 h-2.5" />
          </button>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pl-6">
        {tool.status === 'not_installed' && (
          <ActionBtn icon={<Download className="w-3.5 h-3.5" />} label="安装" onClick={() => {}} accent />
        )}
        {tool.status === 'installed' && (
          <>
            <ActionBtn icon={<Play className="w-3.5 h-3.5" />} label="运行" onClick={() => onRun?.(tool)} accent />
            <ActionBtn icon={<Info className="w-3.5 h-3.5" />} label="详情" onClick={() => setShowDetail(true)} />
            {tool.source === 'user' && (
              <ActionBtn icon={<Edit className="w-3.5 h-3.5" />} label="编辑" onClick={() => onEdit?.(tool)} />
            )}
            <ActionBtn
              icon={<Star className={cn('w-3.5 h-3.5', isFavorited && 'fill-yellow-400 text-yellow-400')} />}
              label={isFavorited ? '取消收藏' : '收藏'}
              onClick={() => (isFavorited ? doUnfavorite(tool.id) : doFavorite(tool.id))}
              active={isFavorited}
            />
            
            {/* Directory button */}
            <ActionBtn
              icon={<FolderOpen className="w-3.5 h-3.5" />}
              label="📂"
              onClick={handleOpenDirectory}
            />

            {/* Publish button (for user tools) */}
            {tool.source === 'user' && (
              <ActionBtn
                icon={<Upload className="w-3.5 h-3.5" />}
                label="发布"
                onClick={() => setShowPublish(true)}
              />
            )}

            {tool.source === 'user' && (
              <ActionBtn icon={<Trash2 className="w-3.5 h-3.5" />} label="删除" onClick={() => doDelete(tool.id)} danger />
            )}
          </>
        )}
        {tool.status === 'update_available' && (
          <>
            <ActionBtn icon={<Play className="w-3.5 h-3.5" />} label="运行" onClick={() => onRun?.(tool)} accent />
          </>
        )}
      </div>
    </div>

    {/* Publish Dialog */}
    <PublishDialog
      open={showPublish}
      itemName={tool.name}
      itemType="tool"
      currentVersion={tool.version}
      onClose={() => setShowPublish(false)}
      onPublish={handlePublish}
    />

    {/* Detail Dialog */}
    <ToolDetailDialog
      tool={tool}
      open={showDetail}
      onClose={() => setShowDetail(false)}
      onPresetsChange={() => useToolsStore.getState().fetchToolsList()}
    />
    </>
  )
}

// ---------- Small action button ----------

function ActionBtn({
  icon,
  label,
  onClick,
  accent,
  danger,
  active,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
  accent?: boolean
  danger?: boolean
  active?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1 px-2 py-1 rounded text-[12px] transition-colors',
        accent && 'bg-accent/20 text-accent hover:bg-accent/30',
        danger && 'text-error hover:bg-error/10',
        active && 'text-accent',
        !accent && !danger && !active && 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary',
      )}
      title={label}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}
