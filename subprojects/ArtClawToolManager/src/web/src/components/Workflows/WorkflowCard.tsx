// Ref: docs/ui/ui-design.md#Workflows
// Workflow card: preview image, name, description, version, source, stats, actions
import { useState } from 'react'
import { Star, Download, Heart, Image, Play, FolderOpen, Upload } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../../utils/cn'
import type { WorkflowItem } from '../../types'
import { useWorkflowsStore } from '../../stores/workflowsStore'
import { useChatStore } from '../../stores/chatStore'
import PublishDialog, { type PublishData } from '../common/PublishDialog'

interface WorkflowCardProps {
  workflow: WorkflowItem
}

const SOURCE_LABEL: Record<string, string> = {
  official: '官方',
  marketplace: '市集',
  user: '我的',
}

const SOURCE_COLOR: Record<string, string> = {
  official: 'bg-accent/20 text-accent',
  marketplace: 'bg-success/20 text-success',
  user: 'bg-warning/20 text-warning',
}

export default function WorkflowCard({ workflow }: WorkflowCardProps) {
  const { doFavorite, doUnfavorite } = useWorkflowsStore()
  const navigate = useNavigate()
  const [showPublish, setShowPublish] = useState(false)

  const isFavorited = workflow.runtimeStatus?.favorited ?? false

  const handleFavorite = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (isFavorited) {
      doUnfavorite(workflow.id)
    } else {
      doFavorite(workflow.id)
    }
  }

  const handleRun = () => {
    const { setExecutionContext, setPrefill } = useChatStore.getState()
    const params = workflow.parameters ?? []
    const defaults: Record<string, unknown> = {}
    for (const p of params) {
      if (p.default !== undefined) defaults[p.id] = p.default
    }
    setExecutionContext({
      type: 'workflow',
      id: workflow.id,
      name: workflow.name,
      parameters: params,
      values: defaults,
      needsAI: true, // Workflows always need AI
    })
    
    // Set prefill message
    setPrefill(
      `请帮我运行 Workflow "${workflow.name}"`,
      `配置 Workflow "${workflow.name}" 的参数`
    )
    
    navigate('/')
  }

  const handleOpenDirectory = async () => {
    try {
      await fetch(`/api/v1/workflows/${workflow.id}/open-dir`, {
        method: 'POST',
      })
    } catch (error) {
      console.error('Failed to open directory:', error)
    }
  }

  const handlePublish = async (data: PublishData) => {
    try {
      await fetch(`/api/v1/workflows/${workflow.id}/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      // 刷新 workflows 列表
      useWorkflowsStore.getState().fetchWorkflowsList()
    } catch (error) {
      console.error('Failed to publish workflow:', error)
      throw error
    }
  }

  return (
    <>
      <div
        className={cn(
          'group rounded-lg border border-border-default bg-bg-secondary',
          'hover:border-border-hover transition-colors overflow-hidden',
        )}
      >
        {/* Preview Image */}
        <div className="relative w-full h-36 bg-bg-tertiary flex items-center justify-center overflow-hidden">
          {workflow.previewImage ? (
            <img
              src={workflow.previewImage}
              alt={workflow.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <Image className="w-10 h-10 text-text-dim opacity-30" />
          )}
          {/* Favorite button overlay */}
          <button
            onClick={handleFavorite}
            className={cn(
              'absolute top-2 right-2 p-1.5 rounded-full transition-all',
              'bg-bg-primary/60 backdrop-blur-sm',
              isFavorited
                ? 'text-error'
                : 'text-text-dim opacity-0 group-hover:opacity-100 hover:text-error',
            )}
            title={isFavorited ? '取消收藏' : '收藏'}
          >
            <Heart className={cn('w-4 h-4', isFavorited && 'fill-error')} />
          </button>
          {/* Source badge overlay */}
          <span
            className={cn(
              'absolute top-2 left-2 text-[10px] px-2 py-0.5 rounded-full',
              SOURCE_COLOR[workflow.source],
            )}
          >
            {SOURCE_LABEL[workflow.source]}
          </span>
        </div>

        {/* Content */}
        <div className="p-4">
          {/* Title */}
          <h3 className="text-body font-medium text-text-primary truncate mb-1">
            {workflow.name}
          </h3>

          {/* Description */}
          <p className="text-small text-text-secondary line-clamp-2 mb-3 min-h-[2.5em]">
            {workflow.description}
          </p>

          {/* Meta */}
          <div className="flex items-center gap-2 text-[11px] text-text-dim mb-3">
            {workflow.version && <span>v{workflow.version}</span>}
            {workflow.stats.rating > 0 && (
              <>
                <span>·</span>
                <span className="flex items-center gap-0.5">
                  <Star className="w-3 h-3 fill-warning text-warning" />
                  {workflow.stats.rating}
                </span>
              </>
            )}
            {workflow.stats.downloads > 0 && (
              <>
                <span>·</span>
                <span className="flex items-center gap-0.5">
                  <Download className="w-3 h-3" />
                  {workflow.stats.downloads >= 1000
                    ? `${(workflow.stats.downloads / 1000).toFixed(1)}k`
                    : workflow.stats.downloads}
                </span>
              </>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleRun}
              className={cn(
                'flex items-center gap-1 px-3 py-1.5 rounded text-[12px] transition-colors',
                'bg-accent/20 text-accent hover:bg-accent/30',
              )}
            >
              <Play className="w-3.5 h-3.5" />
              <span>运行</span>
            </button>
            <button
              onClick={handleOpenDirectory}
              className={cn(
                'flex items-center gap-1 px-2 py-1.5 rounded text-[12px] transition-colors',
                'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary',
              )}
              title="打开目录"
            >
              <FolderOpen className="w-3.5 h-3.5" />
            </button>
            {workflow.source === 'user' && (
              <button
                onClick={() => setShowPublish(true)}
                className={cn(
                  'flex items-center gap-1 px-2 py-1.5 rounded text-[12px] transition-colors',
                  'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary',
                )}
                title="发布"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>发布</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Publish Dialog */}
      <PublishDialog
        open={showPublish}
        itemName={workflow.name}
        itemType="workflow"
        currentVersion={workflow.version}
        onClose={() => setShowPublish(false)}
        onPublish={handlePublish}
      />
    </>
  )
}
