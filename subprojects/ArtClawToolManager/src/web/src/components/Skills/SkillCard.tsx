// Ref: docs/ui/ui-design.md#Skills
// Skill card: name, description, version, source, status, sync status, action buttons
import { Star, Download, Pin, Ban, Trash2, RefreshCw, CheckCircle, FolderOpen, ArrowDownToLine, ArrowUpFromLine, AlertTriangle } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { cn } from '../../utils/cn'
import type { SkillItem, SyncStatus } from '../../types'
import { useSkillsStore } from '../../stores/skillsStore'
import { useAppStore } from '../../stores/appStore'
import PublishDialog from '../common/PublishDialog'
import type { PublishData } from '../common/PublishDialog'

interface SkillCardProps {
  skill: SkillItem
}

const STATUS_BADGE: Record<string, { zh: string; en: string; color: string }> = {
  installed:         { zh: '已安装', en: 'Installed',  color: 'bg-green-500/20 text-green-400' },
  not_installed:     { zh: '可安装', en: 'Available',  color: 'bg-gray-700 text-gray-400' },
  update_available:  { zh: '有更新', en: 'Update',     color: 'bg-yellow-500/20 text-yellow-400' },
  disabled:          { zh: '已禁用', en: 'Disabled',   color: 'bg-red-500/20 text-red-400' },
}

const SOURCE_BADGE: Record<string, { zh: string; en: string; color: string }> = {
  official:     { zh: '官方', en: 'Official',     color: 'text-blue-400' },
  marketplace:  { zh: '市集', en: 'Marketplace',  color: 'text-purple-400' },
  user:         { zh: '我的', en: 'Mine',          color: 'text-green-400' },
}

const SYNC_BADGE: Record<SyncStatus, { zh: string; en: string; color: string } | null> = {
  synced:           null, // Don't show anything when synced
  not_installed:    null, // Status badge already shows "可安装"
  source_newer:     { zh: '源码有更新', en: 'Source Updated',  color: 'bg-yellow-500/20 text-yellow-400' },
  installed_newer:  { zh: '本地版本新', en: 'Local Newer',     color: 'bg-blue-500/20 text-blue-400' },
  modified:         { zh: '本地已修改', en: 'Local Modified',  color: 'bg-blue-500/20 text-blue-400' },
  conflict:         { zh: '存在冲突',   en: 'Conflict',        color: 'bg-red-500/20 text-red-400' },
  no_source:        { zh: '无源码',     en: 'No Source',       color: 'bg-gray-700/50 text-gray-500' },
}

// Format relative time (e.g., "2天前", "3 hours ago")
function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMinutes = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffMinutes < 60) {
      return diffMinutes <= 1 ? '刚刚' : `${diffMinutes}分钟前`
    } else if (diffHours < 24) {
      return `${diffHours}小时前`
    } else if (diffDays < 30) {
      return `${diffDays}天前`
    } else {
      return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' })
    }
  } catch {
    return ''
  }
}

export default function SkillCard({ skill }: SkillCardProps) {
  const { selectedSkillIds, toggleSelectSkill, doInstall, doUninstall, doEnable, doDisable, doPin, doUnpin, doUpdate, doSyncFromSource, doPublishToSource } =
    useSkillsStore()
  const language = useAppStore((s) => s.language)
  const [showDirectoryDropdown, setShowDirectoryDropdown] = useState(false)
  const [showPublish, setShowPublish] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const isSelected = selectedSkillIds.has(skill.id)
  const badge = STATUS_BADGE[skill.status] ?? STATUS_BADGE.installed
  const source = SOURCE_BADGE[skill.source] ?? SOURCE_BADGE.official
  const isPinned = skill.runtimeStatus?.pinned ?? false
  const syncStatus = skill.syncStatus ?? 'no_source'
  const syncBadge = SYNC_BADGE[syncStatus]

  const t = (zh: string, en: string) => language === 'zh' ? zh : en

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDirectoryDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleOpenDirectory = async (type: 'installed' | 'source') => {
    setShowDirectoryDropdown(false)
    try {
      const endpoint = type === 'source' ? 'open-source-dir' : 'open-dir'
      await fetch(`/api/v1/skills/${skill.id}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    } catch (error) {
      console.error('Failed to open directory:', error)
    }
  }

  const handlePublish = async (data: PublishData) => {
    await doPublishToSource(skill.id, {
      version: data.version,
      description: data.description,
      target: data.target,
      dcc: data.dcc,
    })
  }

  // Infer DCC dir from sourcePath: ...skills/{layer}/{dcc}/{name}
  const inferredDcc = (() => {
    if (!skill.sourcePath) return 'universal'
    const parts = skill.sourcePath.replace(/\\/g, '/').split('/')
    const idx = parts.lastIndexOf('skills')
    // parts[idx+1]=layer, parts[idx+2]=dcc
    return idx >= 0 && parts[idx + 2] ? parts[idx + 2] : 'universal'
  })()

  return (
    <div
      className={cn(
        'group relative rounded-lg border p-4 transition-colors',
        isSelected
          ? 'border-blue-500 bg-blue-500/5'
          : 'border-gray-700 bg-gray-800 hover:border-gray-500',
      )}
    >
      {/* Checkbox */}
      <div
        className={cn(
          'absolute top-3 left-3 transition-opacity',
          isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
        )}
      >
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => toggleSelectSkill(skill.id)}
          className="w-4 h-4 rounded cursor-pointer"
        />
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0 pl-6">
          <span className="text-sm font-medium text-gray-200 truncate">{skill.name}</span>
          {/* DCC tags */}
          {skill.targetDCCs.length > 0 && (
            <span className="text-[10px] text-gray-500">{skill.targetDCCs.join(', ')}</span>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Sync status badge */}
          {syncBadge && (
            <span className={cn('text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-1', syncBadge.color)}>
              {syncStatus === 'conflict' && <AlertTriangle className="w-2.5 h-2.5" />}
              {syncStatus === 'source_newer' && <ArrowDownToLine className="w-2.5 h-2.5" />}
              {(syncStatus === 'installed_newer' || syncStatus === 'modified') && <ArrowUpFromLine className="w-2.5 h-2.5" />}
              {language === 'zh' ? syncBadge.zh : syncBadge.en}
            </span>
          )}
          <span className={cn('text-[11px] px-2 py-0.5 rounded-full', badge.color)}>
            {language === 'zh' ? badge.zh : badge.en}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-gray-400 mb-3 line-clamp-2 pl-6">{skill.description}</p>

      {/* Meta */}
      <div className="flex items-center gap-2 text-[11px] text-gray-500 mb-3 pl-6">
        <span className={source.color}>{language === 'zh' ? source.zh : source.en}</span>
        {skill.author && (
          <>
            <span>·</span>
            <span>{skill.author}</span>
          </>
        )}
        <span>·</span>
        <span>v{skill.version}</span>
        {skill.updatedAt && (
          <>
            <span>·</span>
            <span>{formatRelativeTime(skill.updatedAt)}</span>
          </>
        )}
        {skill.stats.rating > 0 && (
          <>
            <span>·</span>
            <span className="flex items-center gap-0.5">
              <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
              {skill.stats.rating}
            </span>
          </>
        )}
        {skill.stats.downloads > 0 && (
          <>
            <span>·</span>
            <span className="flex items-center gap-0.5">
              <Download className="w-3 h-3" />
              {skill.stats.downloads >= 1000
                ? `${(skill.stats.downloads / 1000).toFixed(1)}k`
                : skill.stats.downloads}
            </span>
          </>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pl-6 flex-wrap">
        {skill.status === 'not_installed' && (
          <ActionBtn icon={<Download className="w-3.5 h-3.5" />} label={t('安装', 'Install')} onClick={() => doInstall(skill.id)} accent />
        )}
        {skill.status === 'installed' && (
          <>
            <ActionBtn icon={<Ban className="w-3.5 h-3.5" />} label={t('禁用', 'Disable')} onClick={() => doDisable(skill.id)} />
            <ActionBtn icon={<Trash2 className="w-3.5 h-3.5" />} label={t('卸载', 'Uninstall')} onClick={() => doUninstall(skill.id)} danger />
            <ActionBtn
              icon={<Pin className={cn('w-3.5 h-3.5', isPinned && 'fill-blue-400 text-blue-400')} />}
              label={isPinned ? t('取消钉选', 'Unpin') : t('钉选', 'Pin')}
              onClick={() => (isPinned ? doUnpin(skill.id) : doPin(skill.id))}
              active={isPinned}
            />
          </>
        )}
        {skill.status === 'update_available' && (
          <>
            <ActionBtn icon={<RefreshCw className="w-3.5 h-3.5" />} label={t('更新', 'Update')} onClick={() => doUpdate(skill.id)} accent />
            <ActionBtn icon={<Trash2 className="w-3.5 h-3.5" />} label={t('卸载', 'Uninstall')} onClick={() => doUninstall(skill.id)} danger />
          </>
        )}
        {skill.status === 'disabled' && (
          <>
            <ActionBtn icon={<CheckCircle className="w-3.5 h-3.5" />} label={t('启用', 'Enable')} onClick={() => doEnable(skill.id)} accent />
            <ActionBtn icon={<Trash2 className="w-3.5 h-3.5" />} label={t('卸载', 'Uninstall')} onClick={() => doUninstall(skill.id)} danger />
          </>
        )}

        {/* Sync actions */}
        {syncStatus === 'source_newer' && (
          <ActionBtn
            icon={<ArrowDownToLine className="w-3.5 h-3.5" />}
            label={t('更新', 'Update')}
            onClick={() => doSyncFromSource(skill.id)}
            accent
          />
        )}
        {(syncStatus === 'installed_newer' || syncStatus === 'modified' || syncStatus === 'no_source') && (
          <ActionBtn
            icon={<ArrowUpFromLine className="w-3.5 h-3.5" />}
            label={t('发布', 'Publish')}
            onClick={() => setShowPublish(true)}
            accent
          />
        )}
        {syncStatus === 'conflict' && (
          <>
            <ActionBtn
              icon={<ArrowDownToLine className="w-3.5 h-3.5" />}
              label={t('用源码覆盖', 'From Source')}
              onClick={() => doSyncFromSource(skill.id)}
            />
            <ActionBtn
              icon={<ArrowUpFromLine className="w-3.5 h-3.5" />}
              label={t('发布到源码', 'To Source')}
              onClick={() => setShowPublish(true)}
            />
          </>
        )}

        {/* Directory dropdown (for installed/update_available/disabled skills, or not_installed with source) */}
        {(skill.status !== 'not_installed' || skill.sourcePath) && (
          <div className="relative" ref={dropdownRef}>
            <ActionBtn
              icon={<FolderOpen className="w-3.5 h-3.5" />}
              label="📂"
              onClick={() => setShowDirectoryDropdown(!showDirectoryDropdown)}
            />
            {showDirectoryDropdown && (
              <div className="absolute right-0 top-8 mt-1 w-48 bg-gray-800 border border-gray-600 rounded-md shadow-lg z-10">
                {skill.status !== 'not_installed' && (
                  <button
                    onClick={() => handleOpenDirectory('installed')}
                    className="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-gray-700 flex items-center gap-2"
                  >
                    <FolderOpen className="w-3 h-3" />
                    {t('打开安装目录', 'Open Install Dir')}
                  </button>
                )}
                {(syncStatus !== 'no_source' || skill.sourcePath) && (
                  <button
                    onClick={() => handleOpenDirectory('source')}
                    className="w-full px-3 py-2 text-left text-xs text-gray-300 hover:bg-gray-700 flex items-center gap-2"
                  >
                    <FolderOpen className="w-3 h-3" />
                    {t('打开源码目录', 'Open Source Dir')}
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Publish dialog */}
      <PublishDialog
        open={showPublish}
        itemName={skill.name}
        itemType="skill"
        currentVersion={skill.version}
        currentDcc={inferredDcc}
        currentSource={skill.source}
        currentSourcePath={skill.sourcePath}
        onClose={() => setShowPublish(false)}
        onPublish={handlePublish}
      />
    </div>
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
        accent && 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30',
        danger && 'text-red-400 hover:bg-red-500/10',
        active && 'text-blue-400',
        !accent && !danger && !active && 'text-gray-400 hover:bg-gray-700 hover:text-gray-200',
      )}
      title={label}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}
