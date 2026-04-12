// Ref: docs/ui/ui-design.md#ToolCallCard
// Collapsible tool call card within messages
import { useState } from 'react'
import { ChevronDown, ChevronRight, Wrench, Check, X, Loader2 } from 'lucide-react'
import type { ToolCall } from '../../types'

interface ToolCallCardProps {
  toolCall: ToolCall
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending: <Loader2 className="w-3.5 h-3.5 animate-spin text-text-dim" />,
  running: <Loader2 className="w-3.5 h-3.5 animate-spin text-warning" />,
  completed: <Check className="w-3.5 h-3.5 text-success" />,
  error: <X className="w-3.5 h-3.5 text-error" />,
}

export default function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="my-2 rounded border border-border-default bg-msg-tool overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-small hover:bg-bg-tertiary/30 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-text-dim shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-text-dim shrink-0" />
        )}
        <Wrench className="w-3.5 h-3.5 text-warning shrink-0" />
        <span className="text-text-primary truncate">工具调用: {toolCall.name}</span>
        <div className="flex-1" />
        {STATUS_ICON[toolCall.status]}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-border-default/50">
          {/* Arguments */}
          <div className="mt-2">
            <span className="text-[11px] text-text-dim">参数:</span>
            <pre className="mt-1 p-2 rounded bg-bg-primary text-code font-mono text-[12px] text-text-secondary overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>

          {/* Result */}
          {toolCall.result && (
            <div>
              <span className="text-[11px] text-text-dim">结果:</span>
              <pre className="mt-1 p-2 rounded bg-msg-tool-result text-code font-mono text-[12px] text-text-secondary overflow-x-auto">
                {toolCall.result}
              </pre>
            </div>
          )}

          {/* Error */}
          {toolCall.error && (
            <div>
              <span className="text-[11px] text-error">错误:</span>
              <pre className="mt-1 p-2 rounded bg-msg-tool-error text-code font-mono text-[12px] text-error overflow-x-auto">
                {toolCall.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
