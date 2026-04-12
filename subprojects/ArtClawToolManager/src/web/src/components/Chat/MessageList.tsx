// Ref: docs/ui/ui-design.md#MessageList
// Message list: user / AI / system / tool messages with markdown-like rendering
import { useEffect, useRef } from 'react'
import { User, Bot, Settings as SettingsIcon, Loader2 } from 'lucide-react'
import { cn } from '../../utils/cn'
import { useChatStore } from '../../stores/chatStore'
import ToolCallCard from './ToolCallCard'
import type { ChatMessage } from '../../types'

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

      {/* Content */}
      <div className="text-body text-text-primary whitespace-pre-wrap break-words leading-relaxed">
        {msg.content}
        {msg.isStreaming && (
          <span className="inline-block ml-1 animate-pulse-slow">▌</span>
        )}
      </div>

      {/* Tool calls */}
      {msg.toolCalls?.map((tc) => (
        <ToolCallCard key={tc.id} toolCall={tc} />
      ))}

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
