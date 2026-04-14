// Ref: docs/ui/ui-design.md#RightPanel
// Ref: docs/features/parameter-panel-interaction.md
// Right panel: parameter panel (when executionContext active) or recent used items
import { Clock, Play, Loader2 } from 'lucide-react'
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../../utils/cn'
import ParameterPanel from '../Chat/ParameterPanel'
import { useChatStore } from '../../stores/chatStore'
import { useToolsStore } from '../../stores/toolsStore'
import { useAppStore } from '../../stores/appStore'
import { fetchRecentSkills, fetchRecentWorkflows, fetchRecentTools, fetchToolDetail, fetchWorkflowDetail } from '../../api/client'
import type { ToolItemExtended, WorkflowDetail } from '../../types'

interface RecentItem {
  id: string
  name: string
  type: 'skill' | 'workflow' | 'tool'
  lastUsed: string
}

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
  const sendMessage = useChatStore((s) => s.sendMessage)
  const language = useAppStore((s) => s.language)
  const navigate = useNavigate()
  
  const doUnpin = useToolsStore((s) => s.doUnpin)
  const doPin = useToolsStore((s) => s.doPin)
  const [recentItems, setRecentItems] = useState<RecentItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [runningId, setRunningId] = useState<string | null>(null)

  // Resizable width state
  const [width, setWidth] = useState(() => {
    const saved = localStorage.getItem('artclaw_right_panel_width')
    return saved ? parseInt(saved, 10) : 280
  })
  const [isDragging, setIsDragging] = useState(false)

  // Load recent items from API
  const loadRecent = useCallback(async () => {
    setIsLoading(true)
    try {
      const [skills, workflows, tools] = await Promise.allSettled([
        fetchRecentSkills(5),
        fetchRecentWorkflows(5),
        fetchRecentTools(5),
      ])
      const items: RecentItem[] = []
      const toItems = (result: PromiseSettledResult<any[]>, type: RecentItem['type']) => {
        if (result.status === 'fulfilled' && Array.isArray(result.value)) {
          return result.value.map((x: any) => ({
            id: x.id ?? x.name,
            name: x.name,
            type,
            lastUsed: x.last_used ?? x.updatedAt ?? x.updated_at ?? '',
          }))
        }
        return []
      }
      // fetchRecentSkills returns ApiResponse, extract .data
      const skillsData = skills.status === 'fulfilled'
        ? (Array.isArray((skills.value as any)?.data) ? (skills.value as any).data : [])
        : []
      const skillItems: RecentItem[] = skillsData.map((x: any) => ({
        id: x.id ?? x.name,
        name: x.name,
        type: 'skill' as const,
        lastUsed: x.last_used ?? x.updatedAt ?? x.updated_at ?? '',
      }))
      items.push(...skillItems, ...toItems(workflows, 'workflow'), ...toItems(tools, 'tool'))
      items.sort((a, b) => (new Date(b.lastUsed).getTime() || 0) - (new Date(a.lastUsed).getTime() || 0))
      setRecentItems(items.slice(0, 10))
    } catch {
      setRecentItems([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { loadRecent() }, [loadRecent])

  // 最近使用的运行按钮 — 逻辑与 Tools 页 handleRun 一致
  const handleRun = useCallback(async (item: RecentItem) => {
    const { setExecutionContext, setPrefill } = useChatStore.getState()

    if (item.type === 'tool') {
      setRunningId(item.id)
      try {
        const res = await fetchToolDetail(item.id)
        const tool = res.data as ToolItemExtended | undefined
        if (!tool) { sendMessage(`/run tool:${item.id}`); return }

        doPin(item.id)

        const params = (tool.manifest?.inputs ?? []).map((inp) => ({
          id: inp.id,
          name: inp.name,
          type: inp.type as 'string' | 'number' | 'boolean' | 'enum' | 'select' | 'image',
          required: inp.required,
          default: inp.default,
          min: inp.min,
          max: inp.max,
          step: inp.step,
          options: inp.options,
          description: inp.description,
        }))
        const defaults: Record<string, unknown> = {}
        for (const p of params) {
          if (p.default !== undefined) defaults[p.id] = p.default
        }
        let needsAI = false
        if (tool.implementationType === 'skill_wrapper') needsAI = true
        else if (tool.implementationType === 'composite') {
          needsAI = (tool.manifest?.implementation?.tools ?? []).some((t: string) => t.startsWith('skill:'))
        }
        setExecutionContext({ type: 'tool', id: tool.id, name: tool.name, parameters: params, values: defaults, needsAI })
        setPrefill(`请帮我运行工具 "${tool.name}"`, `配置工具 "${tool.name}" 的参数`)
        navigate('/')
      } catch {
        sendMessage(`/run tool:${item.id}`)
      } finally {
        setRunningId(null)
      }
    } else if (item.type === 'workflow') {
      setRunningId(item.id)
      try {
        const res = await fetchWorkflowDetail(item.id)
        const wf = res.data as WorkflowDetail | undefined
        if (!wf) { sendMessage(`/run workflow:${item.id}`); return }

        const params = (wf.parameters ?? [])
        const defaults: Record<string, unknown> = {}
        for (const p of params) {
          if (p.default !== undefined) defaults[p.id] = p.default
        }
        setExecutionContext({ type: 'workflow', id: wf.id, name: wf.name, parameters: params, values: defaults })
        setPrefill(`请帮我运行工作流 "${wf.name}"`, `配置工作流 "${wf.name}" 的参数`)
        navigate('/')
      } catch {
        sendMessage(`/run workflow:${item.id}`)
      } finally {
        setRunningId(null)
      }
    } else {
      // skill — 直接发消息触发
      sendMessage(`/run skill:${item.id}`)
    }
  }, [sendMessage, doPin, navigate])

  // Save width to localStorage when it changes
  useEffect(() => {
    localStorage.setItem('artclaw_right_panel_width', width.toString())
  }, [width])

  // Auto-expand when executionContext is active (parameters or tool with triggers)
  useEffect(() => {
    if (executionContext) {
      const isTool = executionContext.type === 'tool'
      // Tools need more width for trigger rule editor; workflows need it for parameters
      const minWidth = isTool ? 420 : (executionContext.parameters.length > 0 ? 380 : 280)
      if (width < minWidth) {
        setWidth(minWidth)
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
    const clampedWidth = Math.min(Math.max(newWidth, 240), 700) // Min 240px, Max 700px
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
            {isLoading && (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-4 h-4 animate-spin text-text-dim" />
              </div>
            )}
            {!isLoading && recentItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-text-dim text-sm">
                <Clock className="w-8 h-8 mb-2 opacity-30" />
                <p>{language === 'zh' ? '暂无最近使用记录' : 'No recent items'}</p>
              </div>
            ) : (
              recentItems.map((item) => (
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
                    onClick={() => handleRun(item)}
                    disabled={runningId === item.id}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-bg-quaternary text-text-dim hover:text-accent transition-all disabled:cursor-wait"
                    title={language === 'zh' ? '运行' : 'Run'}
                  >
                    {runningId === item.id
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <Play className="w-3.5 h-3.5" />
                    }
                  </button>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </aside>
  )
}
