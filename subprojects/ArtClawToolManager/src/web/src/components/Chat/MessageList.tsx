// Ref: docs/ui/ui-design.md#MessageList
// Message list: user / AI / system / tool messages with markdown rendering + tool call grouping
import { useState, useEffect, useRef } from 'react'
import { User, Bot, Settings as SettingsIcon, Loader2, ChevronDown, ChevronRight, Wrench } from 'lucide-react'
import { cn } from '../../utils/cn'
import { useChatStore } from '../../stores/chatStore'
import ToolCallCard from './ToolCallCard'
import MarkdownRenderer from './MarkdownRenderer'
import type { ChatMessage, ToolCall } from '../../types'

// ---------- Tool calls group (collapsible) ----------

function ToolCallGroup({ toolCalls }: { toolCalls: ToolCall[] }) {
  const [expanded, setExpanded] = useState(false)
  const count = toolCalls.length

  // 1-2 个 tool call 直接展示，不需要分组
  if (count <= 2) {
    return (
      <>
        {toolCalls.map((tc) => (
          <ToolCallCard key={tc.id} toolCall={tc} />
        ))}
      </>
    )
  }

  // 3+ 个 tool call 分组折叠
  const doneCount = toolCalls.filter((t) => t.status === 'completed').length
  const errorCount = toolCalls.filter((t) => t.status === 'error').length
  const runningCount = toolCalls.filter((t) => t.status === 'running' || t.status === 'pending').length

  const summaryParts: string[] = []
  if (doneCount > 0) summaryParts.push(`${doneCount} 完成`)
  if (errorCount > 0) summaryParts.push(`${errorCount} 错误`)
  if (runningCount > 0) summaryParts.push(`${runningCount} 运行中`)
  const summary = summaryParts.join(', ')

  return (
    <div className="my-2 rounded border border-border-default bg-msg-tool/50 overflow-hidden">
      {/* Group header */}
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
        <span className="text-text-primary">{count} 次工具调用</span>
        <span className="text-text-dim text-[11px]">({summary})</span>
      </button>

      {/* Expanded list with scrollable container */}
      {expanded && (
        <div className="max-h-[400px] overflow-y-auto border-t border-border-default/50 px-1 py-1 space-y-1">
          {toolCalls.map((tc) => (
            <ToolCallCard key={tc.id} toolCall={tc} />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------- Single message bubble ----------

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const roleConfig: Record<string, { icon: React.ReactNode; bg: string; border: string; label: string }> = {
    user: {
      icon: <User className="w-4 h-4" />,
      bg: 'bg-msg-user',
      border: 'border-l-success',
      label: '用户',
    },
    assistant: {
      icon: <Bot className="w-4 h-4" />,
      bg: 'bg-msg-assistant',
      border: 'border-l-accent',
      label: 'AI',
    },
    system: {
      icon: <SettingsIcon className="w-4 h-4" />,
      bg: 'bg-msg-system',
      border: 'border-l-text-dim',
      label: '系统',
    },
    tool: {
      icon: <SettingsIcon className="w-4 h-4" />,
      bg: 'bg-msg-tool',
      border: 'border-l-warning',
      label: '工具',
    },
  }

  const config = roleConfig[msg.role] ?? roleConfig.system

  const time = new Date(msg.timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className={cn('rounded-lg p-3 border-l-[3px] animate-fade-in', config.bg, config.border)}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-text-dim">{config.icon}</span>
        <span className="text-small font-medium text-text-primary">{config.label}</span>
        <span className="flex-1" />
        <span className="text-[11px] text-text-dim">{time}</span>
      </div>

      {/* Content — markdown rendered for assistant, plain for others */}
      {msg.content && (
        msg.role === 'assistant' || msg.role === 'system' ? (
          <MarkdownRenderer content={msg.content} />
        ) : (
          <div className="text-body text-text-primary whitespace-pre-wrap break-words leading-relaxed">
            {msg.content}
          </div>
        )
      )}

      {/* Streaming cursor */}
      {msg.isStreaming && (
        <span className="inline-block ml-1 animate-pulse-slow text-text-primary">▌</span>
      )}

      {/* Tool calls — grouped when 3+ */}
      {msg.toolCalls && msg.toolCalls.length > 0 && (
        <ToolCallGroup toolCalls={msg.toolCalls} />
      )}

      {/* Images */}
      {msg.images?.map((url, i) => (
        <div key={i} className="mt-2">
          <img
            src={url}
            alt="attachment"
            className="max-w-full max-h-64 rounded border border-border-default"
            loading="lazy"
          />
        </div>
      ))}
    </div>
  )
}

// ---------- Main component ----------

export default function MessageList() {
  const { messages, isTyping } = useChatStore()
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, isTyping])

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-text-dim">
          <Bot className="w-12 h-12 mb-3 opacity-30" />
          <p className="text-body">开始一段新对话</p>
          <p className="text-small mt-1">输入消息或使用 / 命令</p>
        </div>
      )}

      {messages.map((msg) => (
        <MessageBubble key={msg.id} msg={msg} />
      ))}

      {/* Typing indicator */}
      {isTyping && (
        <div className="flex items-center gap-2 px-3 py-2 text-small text-text-dim animate-fade-in">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>AI 正在思考...</span>
        </div>
      )}
    </div>
  )
}
