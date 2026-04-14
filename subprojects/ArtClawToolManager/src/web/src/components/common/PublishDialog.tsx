// Ref: docs/specs/architecture-design.md#版本管理
// Publish dialog: target layer, DCC dir, version, description
import { useState, useEffect } from 'react'
import { X, Upload } from 'lucide-react'
import { cn } from '../../utils/cn'

export interface PublishDialogProps {
  open: boolean
  itemName: string
  itemType: 'workflow' | 'tool' | 'skill'
  currentVersion?: string
  currentDcc?: string        // default DCC directory inferred from skill
  currentSource?: string     // skill.source ('official' | 'marketplace' | 'user')
  currentSourcePath?: string // skill.source_path — authoritative when non-empty
  onClose: () => void
  onPublish: (data: PublishData) => void
}

export interface PublishData {
  target: 'official' | 'marketplace'
  dcc: string
  version: string
  description: string
}

const DCC_OPTIONS = [
  { value: 'universal',            label: 'Universal' },
  { value: 'unreal',               label: 'UE' },
  { value: 'maya',                 label: 'Maya' },
  { value: 'max',                  label: 'Max' },
  { value: 'blender',              label: 'Blender' },
  { value: 'houdini',              label: 'Houdini' },
  { value: 'substance_designer',   label: 'SD' },
  { value: 'substance_painter',    label: 'SP' },
  { value: 'comfyui',              label: 'ComfyUI' },
]

export default function PublishDialog({
  open,
  itemName,
  itemType,
  currentVersion = '0.1.0',
  currentDcc = 'universal',
  currentSource,
  currentSourcePath,
  onClose,
  onPublish,
}: PublishDialogProps) {
  // Derive the publish target from source_path (authoritative) → source field → default marketplace
  // source_path like "…/skills/official/…" → official
  // source_path like "…/skills/marketplace/…" → marketplace
  // source field 'official' (only trust when source_path also confirms, or no source_path at all)
  const _deriveTarget = (): 'official' | 'marketplace' => {
    if (currentSourcePath) {
      const norm = currentSourcePath.replace(/\\/g, '/')
      if (norm.includes('/skills/official/')) return 'official'
      if (norm.includes('/skills/marketplace/')) return 'marketplace'
    }
    if (currentSource === 'official') return 'official'
    if (currentSource === 'marketplace') return 'marketplace'
    return 'marketplace'
  }

  const [target, setTarget] = useState<'official' | 'marketplace'>(_deriveTarget)
  const [dcc, setDcc] = useState(currentDcc)
  const [version, setVersion] = useState(currentVersion)
  const [description, setDescription] = useState('')
  const [publishing, setPublishing] = useState(false)

  // Re-sync controlled state whenever the dialog opens for a (potentially different) item
  useEffect(() => {
    if (open) {
      setTarget(_deriveTarget())
      setDcc(currentDcc)
      setVersion(currentVersion)
      setDescription('')
    }
  }, [open, currentSource, currentSourcePath, currentDcc, currentVersion])

  if (!open) return null

  const typeName = itemType === 'workflow' ? 'Workflow' : itemType === 'skill' ? 'Skill' : '工具'

  const handlePublish = async () => {
    setPublishing(true)
    try {
      await onPublish({ target, dcc, version, description })
      onClose()
    } catch {
      // error handled by caller
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Dialog */}
      <div className="relative w-[440px] bg-bg-secondary border border-border-default rounded-lg shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
          <div className="flex items-center gap-2">
            <Upload className="w-4 h-4 text-accent" />
            <h3 className="text-body font-medium text-text-primary">发布{typeName}</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-bg-tertiary text-text-dim hover:text-text-primary transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-4">
          {/* Item name */}
          <div>
            <label className="block text-small text-text-secondary mb-1">名称</label>
            <div className="px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small border border-border-default">
              {itemName}
            </div>
          </div>

          {/* Publish target */}
          <div>
            <label className="block text-small text-text-secondary mb-2">发布到</label>
            <div className="flex gap-3">
              {(['official', 'marketplace'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTarget(t)}
                  className={cn(
                    'flex-1 px-3 py-2.5 rounded border text-small text-center transition-colors',
                    target === t
                      ? t === 'official'
                        ? 'bg-accent/15 border-accent text-accent'
                        : 'bg-success/15 border-success text-success'
                      : 'bg-bg-tertiary border-border-default text-text-secondary hover:border-border-hover',
                  )}
                >
                  <div className="font-medium">{t === 'official' ? '官方' : '市集'}</div>
                  <div className="text-[11px] mt-0.5 opacity-70">
                    {t === 'official' ? '项目团队共享 (Git)' : '社区公开分享'}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* DCC directory */}
          <div>
            <label className="block text-small text-text-secondary mb-2">目标 DCC 目录</label>
            <div className="flex flex-wrap gap-1.5">
              {DCC_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setDcc(opt.value)}
                  className={cn(
                    'px-2.5 py-1 rounded text-[12px] border transition-colors',
                    dcc === opt.value
                      ? 'bg-blue-500/20 border-blue-500 text-blue-400'
                      : 'bg-bg-tertiary border-border-default text-text-secondary hover:border-border-hover',
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Version */}
          <div>
            <label className="block text-small text-text-secondary mb-1">版本号</label>
            <input
              type="text"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="1.0.0"
              className={cn(
                'w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small',
                'border border-border-default focus:border-accent focus:outline-none',
                'placeholder:text-text-dim transition-colors',
              )}
            />
            <p className="text-[11px] text-text-dim mt-1">语义化版本: MAJOR.MINOR.PATCH</p>
          </div>

          {/* Description */}
          <div>
            <label className="block text-small text-text-secondary mb-1">更新说明</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述本次发布的变更内容..."
              rows={2}
              className={cn(
                'w-full px-3 py-2 rounded bg-bg-tertiary text-text-primary text-small',
                'border border-border-default focus:border-accent focus:outline-none',
                'placeholder:text-text-dim resize-none transition-colors',
              )}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border-default">
          <button onClick={onClose} className="px-4 py-2 rounded text-small text-text-secondary hover:bg-bg-tertiary transition-colors">
            取消
          </button>
          <button
            onClick={handlePublish}
            disabled={publishing || !version.trim()}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 rounded text-small font-medium transition-colors',
              publishing || !version.trim()
                ? 'bg-accent/30 text-accent/50 cursor-not-allowed'
                : 'bg-accent text-white hover:bg-accent/90',
            )}
          >
            <Upload className="w-3.5 h-3.5" />
            {publishing ? '发布中...' : '发布'}
          </button>
        </div>
      </div>
    </div>
  )
}
