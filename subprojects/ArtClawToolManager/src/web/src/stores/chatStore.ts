// Ref: docs/specs/architecture-design.md#TechStack
// Chat state: WebSocket, messages, sessions
import { create } from 'zustand'
import type { ChatMessage, ChatSession, ContextUsage, ConnectionStatus, ExecutionContext } from '../types'
import { useAppStore } from './appStore'

// Inline SessionEntry (also defined in types/index.ts by another sub-agent)
export interface SessionEntry {
  id: string
  label: string
  sessionKey: string
  cachedMessages: ChatMessage[]
  createdAt: string
  isActive: boolean
}

interface ChatState {
  // Connection
  connectionStatus: ConnectionStatus
  ws: WebSocket | null

  // Session
  sessions: ChatSession[]
  currentSessionId: string | null

  // Messages
  messages: ChatMessage[]
  isTyping: boolean

  // Context
  contextUsage: ContextUsage

  // Prefill (for workflow/tool run redirect)
  prefillMessage: string | null
  prefillGuide: string | null

  // Execution context (drives right panel parameter form)
  executionContext: ExecutionContext | null

  // Cancel/Resume
  cancelledStreamId: string | null

  // Multi-session
  sessionEntries: SessionEntry[]
  activeSessionId: string

  // Actions
  connect: (url: string) => void
  disconnect: () => void
  sendMessage: (content: string) => void
  addMessage: (msg: ChatMessage) => void
  updateMessage: (id: string, partial: Partial<ChatMessage>) => void
  clearMessages: () => void
  setCurrentSession: (id: string) => void
  setSessions: (sessions: ChatSession[]) => void
  setContextUsage: (usage: ContextUsage) => void
  setIsTyping: (typing: boolean) => void
  setPrefill: (message: string, guide: string) => void
  clearPrefill: () => void
  setExecutionContext: (ctx: ExecutionContext) => void
  clearExecutionContext: () => void
  updateParamValues: (values: Record<string, unknown>) => void
  executeWorkflowOrTool: () => void
  cancelRequest: () => void
  resumeReceiving: () => Promise<void>
  createNewSession: () => void
  switchSession: (id: string) => void
  deleteSessionEntry: (id: string) => void
  renameSession: (id: string, label: string) => void
}

let messageIdCounter = 0
function genId(): string {
  messageIdCounter += 1
  return `msg-${Date.now()}-${messageIdCounter}`
}

// Bug 3: Generate unique session labels with counter + time
// Label must match the Gateway displayName format: "ArtClaw TM · <suffix>"
let sessionCounter = 0
function genSessionLabel(): string {
  sessionCounter += 1
  const now = new Date()
  const hhmm = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return `ArtClaw TM · 对话${sessionCounter} · ${hhmm}`
}

// Bug 4: localStorage persistence helpers
const SESSIONS_STORAGE_KEY = 'artclaw_chat_sessions'
const ACTIVE_SESSION_KEY = 'artclaw_active_session'

function loadSessionsFromStorage(): SessionEntry[] {
  try {
    const raw = localStorage.getItem(SESSIONS_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as SessionEntry[]
      return parsed.map(s => ({ ...s, isActive: false })) // reset isActive
    }
  } catch { /* ignore */ }
  return []
}

function saveSessionsToStorage(entries: SessionEntry[]) {
  try {
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(entries))
  } catch { /* ignore */ }
}

function loadActiveSessionId(sessions: SessionEntry[]): string {
  const stored = localStorage.getItem(ACTIVE_SESSION_KEY) ?? 'default'
  return sessions.find(s => s.id === stored) ? stored : (sessions[0]?.id ?? 'default')
}

// Bug 4: Initialize from localStorage before creating store
// Filter out stale entries with default '新对话' label (legacy)
function isValidSession(s: SessionEntry): boolean {
  return typeof s.id === 'string' && typeof s.label === 'string' && s.label !== '新对话'
}

// Check if messages contain a cancelled/stopped assistant message, return its id
function getLastCancelledId(msgs: ChatMessage[]): string | null {
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant' && msgs[i].content.includes('⏹')) {
      return msgs[i].id
    }
  }
  return null
}

const _rawStored = loadSessionsFromStorage()
const _storedSessions = _rawStored.filter(isValidSession)
const _initialActiveId = loadActiveSessionId(_storedSessions)
const _initialSessions: SessionEntry[] = _storedSessions.length > 0
  ? _storedSessions.map(s => ({ ...s, isActive: s.id === _initialActiveId }))
  : [{ id: 'default', label: genSessionLabel(), sessionKey: 'default', cachedMessages: [], createdAt: new Date().toISOString(), isActive: true }]
const _initialMessages = _initialSessions.find(s => s.id === _initialActiveId)?.cachedMessages ?? []
const _initialCancelledStreamId = getLastCancelledId(_initialMessages)

export const useChatStore = create<ChatState>((set, get) => ({
  connectionStatus: 'disconnected',
  ws: null,

  sessions: [],
  currentSessionId: _initialActiveId,

  messages: _initialMessages,
  isTyping: false,

  contextUsage: { used: 0, total: 128000, percentage: 0 },

  prefillMessage: null,
  prefillGuide: null,

  executionContext: null,

  cancelledStreamId: _initialCancelledStreamId,
  // Bug 4: use localStorage-initialized sessions
  sessionEntries: _initialSessions,
  activeSessionId: _initialActiveId,

  connect: (url: string) => {
    const existing = get().ws
    if (existing) existing.close(1000) // deliberate close

    set({ connectionStatus: 'connecting' })
    let reconnectCount = 0
    const MAX_RECONNECT = 5
    const RECONNECT_DELAY_MS = 3000

    const ws = new WebSocket(url)

    ws.onopen = () => {
      reconnectCount = 0
      set({ connectionStatus: 'connected', ws })
    }

    // Bug 2b: clean isTyping on close + auto-reconnect
    ws.onclose = (event) => {
      const msgs = get().messages
      const last = msgs[msgs.length - 1]
      if (last && last.role === 'assistant' && last.isStreaming) {
        get().updateMessage(last.id, { isStreaming: false })
      }
      set({ connectionStatus: 'disconnected', ws: null, isTyping: false })

      if (event.code !== 1000 && event.code !== 1001 && reconnectCount < MAX_RECONNECT) {
        reconnectCount++
        setTimeout(() => {
          const currentWs = get().ws
          if (!currentWs || currentWs.readyState === WebSocket.CLOSED) {
            get().connect(url)
          }
        }, RECONNECT_DELAY_MS)
      } else {
        reconnectCount = 0
      }
    }

    // Bug 2b: clean isTyping on error
    ws.onerror = () => {
      set({ connectionStatus: 'disconnected', ws: null, isTyping: false })
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as Record<string, unknown>
        const msgType = data.type as string

        if (msgType === 'message') {
          // Bug 1: if last message is a streaming assistant message, just mark complete
          const msgs = get().messages
          const last = msgs[msgs.length - 1]
          if (last && last.role === 'assistant' && last.isStreaming) {
            // Stream finished – just mark complete, content already accumulated via chunks
            get().updateMessage(last.id, { isStreaming: false })
            set({ isTyping: false })
          } else {
            // AI / system message from backend (non-streaming)
            const content = (data.content as string) ?? ''
            get().addMessage({
              id: (data.id as string) ?? genId(),
              role: (data.role as ChatMessage['role']) ?? 'assistant',
              content,
              timestamp: new Date().toISOString(),
            })
            set({ isTyping: false })

            // Check for parameter fill directive from Agent
            // Format: <!--artclaw:params {"key":"value",...}-->
            const paramMatch = content.match(/<!--artclaw:params\s+(\{[\s\S]*?\})\s*-->/)
            if (paramMatch) {
              try {
                const paramValues = JSON.parse(paramMatch[1]) as Record<string, unknown>
                const ctx = get().executionContext
                if (ctx) {
                  get().updateParamValues(paramValues)
                }
              } catch {
                // Invalid JSON in directive, ignore
              }
            }
          }
        } else if (msgType === 'message_chunk') {
          // Streaming chunk – append to last assistant message
          const msgs = get().messages
          const last = msgs[msgs.length - 1]
          if (last && last.role === 'assistant' && last.isStreaming) {
            get().updateMessage(last.id, {
              content: last.content + ((data.content as string) ?? ''),
            })
          } else {
            // No streaming message exists yet – create one
            get().addMessage({
              id: (data.id as string) ?? genId(),
              role: 'assistant',
              content: (data.content as string) ?? '',
              timestamp: new Date().toISOString(),
              isStreaming: true,
            })
            set({ isTyping: true })
          }
        } else if (msgType === 'typing') {
          const isTyping = (data.is_typing as boolean) ?? false
          if (!isTyping) {
            // Mark last streaming message as complete
            const msgs = get().messages
            const last = msgs[msgs.length - 1]
            if (last && last.role === 'assistant' && last.isStreaming) {
              get().updateMessage(last.id, { isStreaming: false })
            }
          }
          set({ isTyping })
        } else if (msgType === 'context_usage') {
          set({
            contextUsage: {
              used: (data.total_tokens as number) ?? 0,
              total: 128000,
              percentage: (data.usage_percent as number) ?? 0,
            },
          })
        } else if (msgType === 'message_received') {
          // ACK – no action needed
        } else if (msgType === 'pong') {
          // Heartbeat response – no action needed
        } else if (msgType === 'error') {
          get().addMessage({
            id: genId(),
            role: 'system',
            content: `❌ ${(data.message as string) ?? 'Unknown error'}`,
            timestamp: new Date().toISOString(),
          })
          set({ isTyping: false })
        } else if (msgType === 'clear') {
          get().clearMessages()
        }
      } catch {
        // ignore non-JSON messages
      }
    }
  },

  disconnect: () => {
    const ws = get().ws
    if (ws) ws.close()
    set({ connectionStatus: 'disconnected', ws: null })
  },

  sendMessage: (content: string) => {
    const userMsg: ChatMessage = {
      id: genId(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }
    get().addMessage(userMsg)

    const ws = get().ws

    // If there's an active execution context, attach parameter schema
    // so Agent knows the current form state
    const ctx = get().executionContext
    let enrichedContent = content
    if (ctx) {
      const ctxLines = [
        content,
        '',
        `[当前正在配置 ${ctx.type === 'workflow' ? 'Workflow' : 'Tool'}: "${ctx.name}"]`,
      ]
      // Include tool location and implementation details so AI can locate and execute the tool
      if (ctx.toolPath) {
        ctxLines.push(`工具目录: ${ctx.toolPath}`)
      }
      if (ctx.entryScript) {
        ctxLines.push(`入口脚本: ${ctx.entryScript}`)
      }
      if (ctx.implementationType) {
        ctxLines.push(`实现方式: ${ctx.implementationType}`)
      }
      if (ctx.skillRef) {
        ctxLines.push(`关联 Skill: ${ctx.skillRef}`)
      }
      if (ctx.aiPrompt) {
        ctxLines.push(`AI 执行指引: ${ctx.aiPrompt}`)
      }
      ctxLines.push(
        '参数定义:',
        '```json',
        JSON.stringify(ctx.parameters.map(p => ({
          id: p.id, name: p.name, type: p.type, required: p.required,
          options: p.options, min: p.min, max: p.max, default: p.default,
        })), null, 2),
        '```',
        '当前参数值:',
        '```json',
        JSON.stringify(ctx.values, null, 2),
        '```',
        '',
        '如需帮用户填写参数，请在回复末尾附带:',
        '<!--artclaw:params {"参数id": 值, ...}-->',
      )
      enrichedContent = ctxLines.join('\n')
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      // Include agent_id so backend routes to the correct agent
      const { currentAgent } = useAppStore.getState()
      const payload: Record<string, unknown> = { type: 'chat', content: enrichedContent }
      if (currentAgent) {
        payload.agent_id = currentAgent
      }
      ws.send(JSON.stringify(payload))
      set({ isTyping: true })
    } else {
      // Local mode - add a mock AI response
      setTimeout(() => {
        get().addMessage({
          id: genId(),
          role: 'assistant',
          content: `Echo: ${content}\n\n(Gateway 未连接，这是本地回显消息)`,
          timestamp: new Date().toISOString(),
        })
      }, 1000)
    }
  },

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  updateMessage: (id, partial) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, ...partial } : m)),
    })),

  clearMessages: () => set({ messages: [] }),

  setCurrentSession: (id) => set({ currentSessionId: id }),

  setSessions: (sessions) => set({ sessions }),

  setContextUsage: (usage) => set({ contextUsage: usage }),

  setIsTyping: (typing) => set({ isTyping: typing }),

  setPrefill: (message, guide) => set({ prefillMessage: message, prefillGuide: guide }),

  clearPrefill: () => set({ prefillMessage: null, prefillGuide: null }),

  setExecutionContext: (ctx) => set({ executionContext: ctx }),

  clearExecutionContext: () => set({ executionContext: null }),

  updateParamValues: (values) =>
    set((s) => {
      if (!s.executionContext) return s
      return {
        executionContext: {
          ...s.executionContext,
          values: { ...s.executionContext.values, ...values },
        },
      }
    }),

  executeWorkflowOrTool: () => {
    const { executionContext, addMessage, ws } = get()
    if (!executionContext) return

    const typeName = executionContext.type === 'workflow' ? 'Workflow' : 'Tool'

    // For direct script execution (tools without AI)
    if (executionContext.needsAI === false) {
      // This should be handled in ParameterPanel directly
      return
    }

    // Build structured execution message for Agent
    const execLines = [
      `请执行${typeName} "${executionContext.name}"`,
      '',
    ]
    // Include tool location so AI can find and run the script
    if (executionContext.toolPath) {
      execLines.push(`工具目录: ${executionContext.toolPath}`)
    }
    if (executionContext.entryScript) {
      execLines.push(`入口脚本: ${executionContext.entryScript}`)
    }
    if (executionContext.implementationType) {
      execLines.push(`实现方式: ${executionContext.implementationType}`)
    }
    if (executionContext.skillRef) {
      execLines.push(`关联 Skill: ${executionContext.skillRef}`)
    }
    if (executionContext.aiPrompt) {
      execLines.push(`AI 执行指引: ${executionContext.aiPrompt}`)
    }
    execLines.push(
      '',
      '参数:',
      '```json',
      JSON.stringify(executionContext.values, null, 2),
      '```',
      '',
      '参数定义:',
      '```json',
      JSON.stringify(executionContext.parameters.map(p => ({
        id: p.id, name: p.name, type: p.type, required: p.required,
      })), null, 2),
      '```',
    )
    const execMessage = execLines.join('\n')

    // Add user message to chat
    addMessage({
      id: genId(),
      role: 'user',
      content: `⚙️ 执行 ${typeName} "${executionContext.name}"\n\n参数:\n${JSON.stringify(executionContext.values, null, 2)}`,
      timestamp: new Date().toISOString(),
    })

    // Send to backend via WebSocket (which forwards to Gateway → Agent)
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'chat', content: execMessage }))
      set({ isTyping: true })
    } else {
      // Local mode - mock response
      setTimeout(() => {
        get().addMessage({
          id: genId(),
          role: 'assistant',
          content: `✅ ${typeName} "${executionContext.name}" 执行完成！\n\n(Gateway 未连接，这是模拟执行结果)`,
          timestamp: new Date().toISOString(),
        })
      }, 1000)
    }

    // Clear execution context (panel returns to recent)
    set({ executionContext: null })
  },

  cancelRequest: () => {
    const { ws, messages } = get()
    // Send cancel signal to backend/gateway (agent will be interrupted)
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cancel' }))
    }
    // Immediately clear typing state
    set({ isTyping: false })
    // Mark last streaming/pending assistant message as stopped
    const msgs = [...messages]
    const last = msgs[msgs.length - 1]
    if (last && last.role === 'assistant') {
      set({
        messages: msgs.map((m, i) =>
          i === msgs.length - 1
            ? { ...m, isStreaming: false, content: m.content + (m.content ? '\n\n' : '') + '⏹ *已停止*' }
            : m
        ),
        cancelledStreamId: last.id,
      })
    } else {
      // Typing but no assistant message yet (thinking phase) – just clear
      set({ cancelledStreamId: `cancelled-${Date.now()}` })
    }
  },

  resumeReceiving: async () => {
    const { activeSessionId, sessionEntries } = get()
    // Resume = restore cachedMessages from the current session entry (localStorage)
    const entry = sessionEntries.find(s => s.id === activeSessionId)
    const cached = entry?.cachedMessages ?? []
    if (cached.length > 0) {
      set({ messages: cached, isTyping: false, cancelledStreamId: null })
    } else {
      set({ isTyping: false, cancelledStreamId: null })
    }
  },

  createNewSession: () => {
    const { sessionEntries, activeSessionId, messages } = get()
    // Save current messages to current session entry
    const updated = sessionEntries.map((s) =>
      s.id === activeSessionId ? { ...s, cachedMessages: messages, isActive: false } : s
    )
    // Create new session with unique label (Bug 3)
    const newId = `session-${Date.now()}`
    const newEntry: SessionEntry = {
      id: newId,
      label: genSessionLabel(),
      sessionKey: newId,
      cachedMessages: [],
      createdAt: new Date().toISOString(),
      isActive: true,
    }
    set({
      sessionEntries: [...updated, newEntry],
      activeSessionId: newId,
      messages: [],
      isTyping: false,
      cancelledStreamId: null,
    })
  },

  switchSession: (id: string) => {
    const { sessionEntries, activeSessionId, messages } = get()
    if (id === activeSessionId) return
    // Save current session's messages
    const updated = sessionEntries.map((s) => {
      if (s.id === activeSessionId) return { ...s, cachedMessages: messages, isActive: false }
      if (s.id === id) return { ...s, isActive: true }
      return s
    })
    const target = updated.find((s) => s.id === id)
    const targetMsgs = target?.cachedMessages ?? []
    set({
      sessionEntries: updated,
      activeSessionId: id,
      messages: targetMsgs,
      isTyping: false,
      cancelledStreamId: getLastCancelledId(targetMsgs),
    })
  },

  deleteSessionEntry: (id: string) => {
    const { sessionEntries, activeSessionId } = get()
    if (sessionEntries.length <= 1) return // Don't delete last
    const remaining = sessionEntries.filter((s) => s.id !== id)
    if (id === activeSessionId) {
      // Switch to first remaining
      const next = remaining[0]
      set({
        sessionEntries: remaining.map((s) =>
          s.id === next.id ? { ...s, isActive: true } : s
        ),
        activeSessionId: next.id,
        messages: next.cachedMessages,
        isTyping: false,
      })
    } else {
      set({ sessionEntries: remaining })
    }
  },

  renameSession: (id: string, label: string) => {
    set((s) => ({
      sessionEntries: s.sessionEntries.map((se) =>
        se.id === id ? { ...se, label } : se
      ),
    }))
  },
}))

// Bug 4: Subscribe to store changes and persist sessions to localStorage
useChatStore.subscribe((state) => {
  // Save current messages back to active session before persisting
  const updated = state.sessionEntries.map(s =>
    s.id === state.activeSessionId ? { ...s, cachedMessages: state.messages } : s
  )
  saveSessionsToStorage(updated)
  localStorage.setItem(ACTIVE_SESSION_KEY, state.activeSessionId)
})
