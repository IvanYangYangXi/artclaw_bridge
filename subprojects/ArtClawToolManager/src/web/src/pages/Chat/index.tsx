// Ref: docs/ui/ui-design.md#ChatPage
// Chat page: StatusBar + PinnedSkills + MessageList + QuickInput + ChatInput + Toolbar
import { useState, useEffect, useRef } from 'react'
import { Plus, Paperclip, Square, Send, ChevronDown, Pin, X, Pencil, Zap, Trash2, RotateCcw, MessageSquare } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../../utils/cn'
import StatusBar from '../../components/Chat/StatusBar'
import MessageList from '../../components/Chat/MessageList'
import ChatInput from '../../components/Chat/ChatInput'
import type { ChatInputHandle } from '../../components/Chat/ChatInput'
import { useChatStore } from '../../stores/chatStore'
import { useAppStore } from '../../stores/appStore'
import { useSkillsStore } from '../../stores/skillsStore'

// ---------- Pinned Skills Bar ----------

function PinnedSkillsBar() {
  const skills = useSkillsStore((s) => s.skills)
  const doUnpin = useSkillsStore((s) => s.doUnpin)
  const language = useAppStore((s) => s.language)
  const navigate = useNavigate()

  const pinned = skills.filter((s) => s.runtimeStatus?.pinned)

  if (pinned.length === 0) return null

  return (
    <div className="flex items-center gap-2 px-4 py-1.5 border-b border-gray-700/50 overflow-x-auto">
      <Pin className="w-3 h-3 text-gray-500 shrink-0" />
      {pinned.map((skill) => (
        <span
          key={skill.id}
          className="shrink-0 flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-blue-500/10 text-blue-400 border border-blue-500/20"
        >
          {skill.name}
          <button
            onClick={() => doUnpin(skill.id)}
            className="hover:text-red-400 transition-colors"
            title={language === 'zh' ? '取消钉选' : 'Unpin'}
          >
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}
      <button
        onClick={() => navigate('/skills')}
        className="shrink-0 text-[11px] text-gray-500 hover:text-blue-400 transition-colors"
      >
        {language === 'zh' ? '+ 管理' : '+ manage'}
      </button>
    </div>
  )
}

// ---------- Quick Input Buttons ----------

const DEFAULT_QUICK_INPUTS = [
  '常用提示',
  '创建 Skill',
  '文生图',
  '批量导出',
  '一键渲染',
]

function loadQuickInputs(): string[] {
  try {
    const saved = localStorage.getItem('artclaw_quick_inputs')
    if (saved) return JSON.parse(saved)
  } catch { /* ignore */ }
  return DEFAULT_QUICK_INPUTS
}

function saveQuickInputs(items: string[]) {
  localStorage.setItem('artclaw_quick_inputs', JSON.stringify(items))
}

function QuickInputPanel({ onSelect }: { onSelect: (text: string) => void }) {
  const [items, setItems] = useState(loadQuickInputs)
  const [editing, setEditing] = useState(false)
  const [newItem, setNewItem] = useState('')
  const language = useAppStore((s) => s.language)

  const handleDelete = (idx: number) => {
    const next = items.filter((_, i) => i !== idx)
    setItems(next)
    saveQuickInputs(next)
  }

  const handleAdd = () => {
    const trimmed = newItem.trim()
    if (!trimmed || items.includes(trimmed)) return
    const next = [...items, trimmed]
    setItems(next)
    saveQuickInputs(next)
    setNewItem('')
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-t border-gray-700/50 overflow-x-auto">
      {items.map((text, idx) => (
        <div key={text} className="relative shrink-0 group">
          <button
            onClick={() => !editing && onSelect(text)}
            className={cn(
              'px-3 py-1 rounded-full text-[12px]',
              'bg-gray-800 text-gray-400',
              'hover:bg-blue-500/20 hover:text-blue-400',
              'border border-gray-600 hover:border-blue-500/40',
              'transition-colors',
              editing && 'pr-7',
            )}
          >
            {text}
          </button>
          {editing && (
            <button
              onClick={() => handleDelete(idx)}
              className="absolute -top-1 -right-1 w-4 h-4 bg-red-600 rounded-full flex items-center justify-center"
            >
              <X className="w-2.5 h-2.5 text-white" />
            </button>
          )}
        </div>
      ))}

      {editing && (
        <div className="flex items-center gap-1 shrink-0">
          <input
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder={language === 'zh' ? '新增...' : 'Add...'}
            className="w-24 px-2 py-1 text-[12px] bg-gray-800 text-gray-300 border border-gray-600 rounded-full focus:border-blue-500 focus:outline-none"
          />
        </div>
      )}

      <button
        onClick={() => setEditing(!editing)}
        className={cn(
          'shrink-0 p-1 rounded-full transition-colors',
          editing ? 'text-blue-400 bg-blue-500/20' : 'text-gray-500 hover:text-gray-300',
        )}
        title={language === 'zh' ? '编辑快捷输入' : 'Edit quick inputs'}
      >
        {editing ? <X className="w-3.5 h-3.5" /> : <Pencil className="w-3.5 h-3.5" />}
      </button>
    </div>
  )
}

// ---------- Session Menu ----------

function SessionMenu() {
  const [open, setOpen] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const language = useAppStore((s) => s.language)
  const { sessionEntries, activeSessionId, switchSession, deleteSessionEntry, renameSession, createNewSession } = useChatStore()

  const handleRename = (id: string) => {
    if (renameValue.trim()) {
      renameSession(id, renameValue.trim())
    }
    setRenamingId(null)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded text-sm text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
      >
        <MessageSquare className="w-4 h-4" />
        <span className="max-w-[120px] truncate">
          {sessionEntries.find((s) => s.id === activeSessionId)?.label ?? (language === 'zh' ? '对话' : 'Chat')}
        </span>
        <ChevronDown className="w-3 h-3" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 mb-1 w-64 bg-gray-800 border border-gray-600 rounded-lg shadow-xl z-20 max-h-[300px] flex flex-col">
            <div className="flex-1 overflow-y-auto py-1">
              {sessionEntries.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 text-sm cursor-pointer transition-colors group',
                    s.id === activeSessionId ? 'bg-blue-500/20 text-blue-300' : 'text-gray-300 hover:bg-gray-700',
                  )}
                  onClick={() => { switchSession(s.id); setOpen(false) }}
                >
                  {renamingId === s.id ? (
                    <input
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleRename(s.id)
                        if (e.key === 'Escape') setRenamingId(null)
                      }}
                      onBlur={() => handleRename(s.id)}
                      onClick={(e) => e.stopPropagation()}
                      autoFocus
                      className="flex-1 bg-gray-700 text-gray-200 px-2 py-0.5 rounded text-sm border border-gray-500 focus:border-blue-500 outline-none"
                    />
                  ) : (
                    <span className="flex-1 truncate">{s.label}</span>
                  )}
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => { e.stopPropagation(); setRenamingId(s.id); setRenameValue(s.label) }}
                      className="p-1 rounded hover:bg-gray-600"
                      title={language === 'zh' ? '重命名' : 'Rename'}
                    >
                      <Pencil className="w-3 h-3" />
                    </button>
                    {sessionEntries.length > 1 && (
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteSessionEntry(s.id) }}
                        className="p-1 rounded hover:bg-red-900/50 text-gray-400 hover:text-red-400"
                        title={language === 'zh' ? '删除' : 'Delete'}
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="border-t border-gray-600 p-2">
              <button
                onClick={() => { createNewSession(); setOpen(false) }}
                className="w-full flex items-center gap-1.5 px-3 py-1.5 rounded text-sm text-blue-400 hover:bg-blue-500/10 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                {language === 'zh' ? '新建对话' : 'New Chat'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ---------- Toolbar ----------

function Toolbar({ onNewChat, onSend, isTyping, onStop, onResume, cancelledStreamId }: {
  onNewChat: () => void; onSend: () => void; isTyping: boolean; onStop: () => void;
  onResume: () => void; cancelledStreamId: string | null;
}) {
  const { sendMode, setSendMode } = useAppStore()
  const language = useAppStore((s) => s.language)
  const [showSendMenu, setShowSendMenu] = useState(false)

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-t border-gray-700">
      {/* Left actions */}
      <SessionMenu />
      <button
        onClick={onNewChat}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
      >
        <Plus className="w-4 h-4" />
        <span>{language === 'zh' ? '新对话' : 'New'}</span>
      </button>
      <button
        onClick={() => alert(language === 'zh' ? '附件功能即将推出' : 'Attachment coming soon')}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
      >
        <Paperclip className="w-4 h-4" />
        <span>{language === 'zh' ? '附件' : 'Attach'}</span>
      </button>

      <div className="flex-1" />

      {/* Right actions */}
      {isTyping && (
        <button
          onClick={onStop}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-red-900/50 text-red-300 hover:bg-red-900/80 transition-colors"
        >
          <Square className="w-3.5 h-3.5" />
          <span>{language === 'zh' ? '停止' : 'Stop'}</span>
        </button>
      )}

      {!isTyping && cancelledStreamId && (
        <button
          onClick={onResume}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-blue-900/50 text-blue-300 hover:bg-blue-900/80 transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>{language === 'zh' ? '恢复' : 'Resume'}</span>
        </button>
      )}

      {/* Send button + mode dropdown */}
      <div className="relative flex items-center h-8">
        <button
          onClick={onSend}
          className={cn(
            'flex items-center gap-1.5 px-4 h-full rounded-l text-sm font-medium transition-colors',
            isTyping
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-500',
          )}
          disabled={isTyping}
        >
          <Send className="w-3.5 h-3.5" />
          <span>{isTyping ? (language === 'zh' ? '等待...' : 'Wait...') : (language === 'zh' ? '发送' : 'Send')}</span>
        </button>
        <button
          onClick={() => setShowSendMenu(!showSendMenu)}
          className={cn(
            'flex items-center justify-center px-1.5 h-full rounded-r border-l transition-colors',
            isTyping
              ? 'bg-gray-700 text-gray-500 border-gray-600'
              : 'bg-blue-700 text-white hover:bg-blue-600 border-blue-500',
          )}
        >
          <ChevronDown className="w-3.5 h-3.5" />
        </button>

        {/* Send mode dropdown */}
        {showSendMenu && (
          <div className="absolute bottom-full right-0 mb-1 bg-gray-800 border border-gray-600 rounded shadow-lg z-20 min-w-[160px]">
            <button
              onClick={() => { setSendMode('enter'); setShowSendMenu(false) }}
              className={cn(
                'w-full text-left px-3 py-2 text-xs transition-colors',
                sendMode === 'enter' ? 'text-blue-400 bg-blue-500/10' : 'text-gray-400 hover:bg-gray-700',
              )}
            >
              Enter {language === 'zh' ? '发送' : 'to send'}
            </button>
            <button
              onClick={() => { setSendMode('ctrl-enter'); setShowSendMenu(false) }}
              className={cn(
                'w-full text-left px-3 py-2 text-xs transition-colors',
                sendMode === 'ctrl-enter' ? 'text-blue-400 bg-blue-500/10' : 'text-gray-400 hover:bg-gray-700',
              )}
            >
              Ctrl+Enter {language === 'zh' ? '发送' : 'to send'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------- Chat Page ----------

export default function ChatPage() {
  const { sendMessage, isTyping, prefillMessage, prefillGuide, clearPrefill } = useChatStore()
  const cancelledStreamId = useChatStore((s) => s.cancelledStreamId)
  const sendMode = useAppStore((s) => s.sendMode)
  const chatInputRef = useRef<ChatInputHandle>(null)

  // Load skills for pinned display
  const fetchSkillsList = useSkillsStore((s) => s.fetchSkillsList)
  useEffect(() => { fetchSkillsList() }, [fetchSkillsList])

  const handleSend = (content: string) => {
    sendMessage(content)
    clearPrefill()
  }

  const handleNewChat = () => {
    useChatStore.getState().createNewSession()
    clearPrefill()
  }

  const handleStop = () => {
    useChatStore.getState().cancelRequest()
  }

  const handleResume = () => {
    useChatStore.getState().resumeReceiving()
  }

  const handleQuickInput = (text: string) => {
    sendMessage(text)
  }

  const handleToolbarSend = () => {
    chatInputRef.current?.triggerSend()
  }

  return (
    <div className="flex flex-col h-full bg-gray-900">
      <StatusBar />
      <PinnedSkillsBar />
      <MessageList />
      {/* Prefill guide card */}
      {prefillGuide && (
        <div className="mx-4 mt-2 px-4 py-2.5 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-blue-300">
            <Zap className="w-4 h-4 shrink-0" />
            <span>{prefillGuide}</span>
          </div>
          <button
            onClick={clearPrefill}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
      <QuickInputPanel onSelect={handleQuickInput} />
      <div className="px-4 py-2">
        <ChatInput ref={chatInputRef} onSend={handleSend} sendMode={sendMode} initialValue={prefillMessage ?? undefined} />
      </div>
      <Toolbar onNewChat={handleNewChat} onSend={handleToolbarSend} isTyping={isTyping} onStop={handleStop} onResume={handleResume} cancelledStreamId={cancelledStreamId} />
    </div>
  )
}
