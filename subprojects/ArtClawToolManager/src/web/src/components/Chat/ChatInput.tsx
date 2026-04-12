// Ref: docs/ui/ui-design.md#ChatInput
// Chat input: multi-line, configurable send mode, / command completion
import { useState, useRef, useCallback, useEffect, useImperativeHandle, forwardRef } from 'react'
import { cn } from '../../utils/cn'
import { useChatStore } from '../../stores/chatStore'
import { useAppStore } from '../../stores/appStore'
import type { SlashCommand } from '../../types'
import type { SendMode } from '../../stores/appStore'

const SLASH_COMMANDS: SlashCommand[] = [
  { command: '/connect', description: '连接 OpenClaw Gateway', isLocal: true },
  { command: '/disconnect', description: '断开 Gateway 连接', isLocal: true },
  { command: '/status', description: '查看状态', isLocal: true },
  { command: '/clear', description: '清空聊天记录', isLocal: true },
  { command: '/cancel', description: '取消生成', isLocal: true },
  { command: '/resume', description: '恢复接收', isLocal: true },
  { command: '/new', description: '新对话', isLocal: false },
  { command: '/compact', description: '压缩上下文', isLocal: false },
]

interface ChatInputProps {
  onSend: (content: string) => void
  sendMode?: SendMode
  initialValue?: string
}

export interface ChatInputHandle {
  triggerSend: () => void
}

const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(function ChatInput({ onSend, sendMode = 'enter', initialValue }, ref) {
  const [value, setValue] = useState('')
  const [showCommands, setShowCommands] = useState(false)
  const [commandFilter, setCommandFilter] = useState('')
  const [selectedCmdIdx, setSelectedCmdIdx] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const language = useAppStore((s) => s.language)

  const filteredCommands = SLASH_COMMANDS.filter((c) =>
    c.command.toLowerCase().includes(commandFilter.toLowerCase()),
  )

  // Auto-resize textarea
  const adjustHeight = useCallback(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`
  }, [])

  useEffect(() => {
    adjustHeight()
  }, [value, adjustHeight])

  // Set initial value from prefill
  useEffect(() => {
    if (initialValue) {
      setValue(initialValue)
    }
  }, [initialValue])

  // Expose triggerSend to parent via ref
  useImperativeHandle(ref, () => ({
    triggerSend: () => handleSend(),
  }))

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value
    setValue(v)

    if (v.startsWith('/')) {
      setShowCommands(true)
      setCommandFilter(v)
      setSelectedCmdIdx(0)
    } else {
      setShowCommands(false)
    }
  }

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed) return

    if (trimmed === '/clear') {
      useChatStore.getState().clearMessages()
      setValue('')
      setShowCommands(false)
      return
    }

    onSend(trimmed)
    setValue('')
    setShowCommands(false)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Command navigation
    if (showCommands && filteredCommands.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedCmdIdx((i) => Math.min(i + 1, filteredCommands.length - 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedCmdIdx((i) => Math.max(i - 1, 0))
        return
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && showCommands)) {
        e.preventDefault()
        const cmd = filteredCommands[selectedCmdIdx]
        if (cmd) {
          setValue(cmd.command + ' ')
          setShowCommands(false)
        }
        return
      }
      if (e.key === 'Escape') {
        setShowCommands(false)
        return
      }
    }

    if (e.key === 'Enter') {
      if (sendMode === 'enter') {
        // Enter = send, Shift+Enter = newline
        if (!e.shiftKey) {
          e.preventDefault()
          handleSend()
        }
      } else {
        // Ctrl+Enter = send, Enter = newline
        if (e.ctrlKey || e.metaKey) {
          e.preventDefault()
          handleSend()
        }
      }
    }
  }

  const selectCommand = (cmd: SlashCommand) => {
    setValue(cmd.command + ' ')
    setShowCommands(false)
    textareaRef.current?.focus()
  }

  const placeholderText = sendMode === 'enter'
    ? (language === 'zh' ? '输入消息... (Shift+Enter 换行)' : 'Type a message... (Shift+Enter for newline)')
    : (language === 'zh' ? '输入消息... (Ctrl+Enter 发送)' : 'Type a message... (Ctrl+Enter to send)')

  return (
    <div className="relative">
      {/* Slash command popup */}
      {showCommands && filteredCommands.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 mb-1 bg-gray-800 border border-gray-600 rounded shadow-lg overflow-hidden z-10">
          {filteredCommands.map((cmd, idx) => (
            <button
              key={cmd.command}
              onClick={() => selectCommand(cmd)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 text-sm text-left transition-colors',
                idx === selectedCmdIdx
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-gray-400 hover:bg-gray-700',
              )}
            >
              <code className="font-mono text-blue-400">{cmd.command}</code>
              <span className="text-gray-500">-</span>
              <span className="truncate">{cmd.description}</span>
              {cmd.isLocal && (
                <span className="ml-auto text-[10px] text-gray-500 border border-gray-600 rounded px-1">
                  {language === 'zh' ? '本地' : 'Local'}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholderText}
        rows={1}
        className={cn(
          'w-full px-4 py-3 text-sm text-gray-200',
          'bg-gray-800 rounded',
          'border border-gray-600 focus:border-blue-500 focus:outline-none',
          'placeholder:text-gray-500',
          'transition-colors resize-none',
        )}
      />
    </div>
  )
})

export default ChatInput
