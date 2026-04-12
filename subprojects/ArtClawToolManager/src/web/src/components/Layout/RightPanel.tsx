// Ref: docs/ui/ui-design.md#RightPanel
// Ref: docs/features/parameter-panel-interaction.md
// Right panel: parameter panel (when executionContext active) or recent used items
import { Clock, Play } from 'lucide-react'
import { useState, useEffect, useCallback } from 'react'
import { cn } from '../../utils/cn'
import ParameterPanel from '../Chat/ParameterPanel'
import { useChatStore } from '../../stores/chatStore'
import { useToolsStore } from '../../stores/toolsStore'

interface RecentItem {
  id: string
  name: string
  type: 'skill' | 'workflow' | 'tool'
  lastUsed: string
}

const MOCK_RECENT: RecentItem[] = [
  { id: '1', name: 'comfyui-txt2img', type: 'skill', lastUsed: '2 分钟前' },
  { id: '2', name: 'SDXL 肖像摄影', type: 'workflow', lastUsed: '15 分钟前' },
  { id: '3', name: '批量重命名', type: 'tool', lastUsed: '1 小时前' },
  { id: '4', name: 'comfyui-controlnet', type: 'skill', lastUsed: '3 小时前' },
  { id: '5', name: '一键导出 FBX', type: 'tool', lastUsed: '昨天' },
]

const TYPE_COLORS: Record<string, string> = {
  skill: 'text-accent',
  workflow: 'text-success',
  tool: 'text-warning',
}

const TYPE_LABELS: Record<string, string> = {
  skill: 'Skill',
  workflow: 'Workflow',
  tool: 'Tool',
}

interface RightPanelProps {
  className?: string
}

export default function RightPanel({ className }: RightPanelProps) {
  const executionContext = useChatStore((s) => s.executionContext)
  const updateParamValues = useChatStore((s) => s.updateParamValues)
  const executeWorkflowOrTool = useChatStore((s) => s.executeWorkflowOrTool)
  const clearExecutionContext = useChatStore((s) => s.clearExecutionContext)
  
  const doUnpin = useToolsStore((s) => s.doUnpin)

  // Resizable width state
  const [width, setWidth] = useState(() => {
    const saved = localStorage.getItem('artclaw_right_panel_width')
    return saved ? parseInt(saved, 10) : 280
  })
  const [isDragging, setIsDragging] = useState(false)

  // Save width to localStorage when it changes
  useEffect(() => {
    localStorage.setItem('artclaw_right_panel_width', width.toString())
  }, [width])

  // Auto-expand when executionContext with parameters is active
  useEffect(() => {
    if (executionContext && executionContext.parameters.length > 0) {
      const minParamWidth = 380
      if (width < minParamWidth) {
        setWidth(minParamWidth)
      }
    }
  }, [executionContext])

  // Drag handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return
    
    const newWidth = window.innerWidth - e.clientX
    const clampedWidth = Math.min(Math.max(newWidth, 240), 600) // Min 240px, Max 600px
    setWidth(clampedWidth)
  }, [isDragging])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  // Add/remove event listeners
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  const handleParamChange = (id: string, value: unknown) => {
    updateParamValues({ [id]: value })
  }

  const handleSubmit = () => {
    executeWorkflowOrTool()
  }

  const handleCancel = () => {
    // If it's a tool, unpin it first
    if (executionContext && executionContext.type === 'tool') {
      doUnpin(executionContext.id)
    }
    clearExecutionContext()
  }

  const handleReset = () => {
    if (!executionContext) return
    // Reset to default values
    const defaults: Record<string, unknown> = {}
    for (const p of executionContext.parameters) {
      if (p.default !== undefined) {
        defaults[p.id] = p.default
      }
    }
    updateParamValues(defaults)
  }

  return (
    <aside
      className={cn(
        'h-full bg-bg-secondary border-l border-border-default flex flex-col shrink-0 relative',
        className,
      )}
      style={{ width: `${width}px` }}
    >
      {/* Resize handle */}
      <div
        className={cn(
          'absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize z-10 hover:bg-accent transition-colors',
          isDragging && 'bg-accent'
        )}
        onMouseDown={handleMouseDown}
      />
      
      {executionContext ? (
        <ParameterPanel
          executionContext={executionContext}
          workflowName={executionContext.name}
          parameters={executionContext.parameters}
          values={executionContext.values}
          onChange={handleParamChange}
          onSubmit={handleSubmit}
          onCancel={handleCancel}
          onReset={handleReset}
        />
      ) : (
        <>
          {/* Header */}
          <div className="flex items-center gap-2 px-4 h-12 border-b border-border-default shrink-0">
            <Clock className="w-4 h-4 text-text-dim" />
            <span className="text-small font-medium text-text-primary">最近使用</span>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto py-2">
            {MOCK_RECENT.map((item) => (
              <div
                key={item.id}
                className="group flex items-center gap-3 px-4 py-2.5 hover:bg-bg-tertiary cursor-pointer transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-small text-text-primary truncate">{item.name}</span>
                    <span className={cn('text-[10px] shrink-0', TYPE_COLORS[item.type])}>
                      {TYPE_LABELS[item.type]}
                    </span>
                  </div>
                  <span className="text-[11px] text-text-dim">{item.lastUsed}</span>
                </div>
                <button
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-bg-quaternary text-text-dim hover:text-accent transition-all"
                  title="运行"
                >
                  <Play className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  )
}
