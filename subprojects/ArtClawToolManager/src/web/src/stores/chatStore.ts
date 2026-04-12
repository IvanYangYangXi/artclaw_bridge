// Ref: docs/specs/architecture-design.md#TechStack
// Chat state: WebSocket, messages, sessions
import { create } from 'zustand'
import type { ChatMessage, ChatSession, ContextUsage, ConnectionStatus, ExecutionContext } from '../types'

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
  resumeReceiving: () => void
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

export const useChatStore = create<ChatState>((set, get) => ({
  connectionStatus: 'disconnected',
  ws: null,

  sessions: [
    {
      id: 'default',
      name: '新对话',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messageCount: 0,
    },
  ],
  currentSessionId: 'default',

  messages: [],
  isTyping: false,

  contextUsage: { used: 0, total: 128000, percentage: 0 },

  prefillMessage: null,
  prefillGuide: null,

  executionContext: null,

  cancelledStreamId: null,
  sessionEntries: [
    {
      id: 'default',
      label: '新对话',
      sessionKey: 'default',
      cachedMessages: [],
      createdAt: new Date().toISOString(),
      isActive: true,
    },
  ],
  activeSessionId: 'default',

  connect: (url: string) => {
    const existing = get().ws
    if (existing) existing.close()

    set({ connectionStatus: 'connecting' })
    const ws = new WebSocket(url)

    ws.onopen = () => {
      set({ connectionStatus: 'connected', ws })
    }

    ws.onclose = () => {
      set({ connectionStatus: 'disconnected', ws: null })
    }

    ws.onerror = () => {
      set({ connectionStatus: 'disconnected', ws: null })
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as Record<string, unknown>
        const msgType = data.type as string

        if (msgType === 'message') {
          // AI / system message from backend
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
      enrichedContent = [
        content,
        '',
        `[当前正在配置 ${ctx.type === 'workflow' ? 'Workflow' : 'Tool'}: "${ctx.name}"]`,
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
      ].join('\n')
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'chat', content: enrichedContent }))
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
    const execMessage = [
      `请执行${typeName} "${executionContext.name}"`,
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
    ].join('\n')

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
    // Send cancel to WS
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cancel' }))
    }
    // Clear typing
    set({ isTyping: false })
    // Mark last streaming message as cancelled
    const msgs = [...messages]
    const last = msgs[msgs.length - 1]
    if (last && last.role === 'assistant' && last.isStreaming) {
      set({
        messages: msgs.map((m, i) =>
          i === msgs.length - 1
            ? { ...m, isStreaming: false, content: m.content + '\n\n⏹ *已停止*' }
            : m
        ),
        cancelledStreamId: last.id,
      })
    } else {
      set({ cancelledStreamId: null })
    }
  },

  resumeReceiving: () => {
    const { ws, cancelledStreamId, messages } = get()
    if (cancelledStreamId) {
      // Remove the cancelled marker from the message
      set({
        messages: messages.map((m) =>
          m.id === cancelledStreamId
            ? { ...m, content: m.content.replace('\n\n⏹ *已停止*', ''), isStreaming: true }
            : m
        ),
        isTyping: true,
        cancelledStreamId: null,
      })
      // Send resume to WS
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resume' }))
      }
    }
  },

  createNewSession: () => {
    const { sessionEntries, activeSessionId, messages } = get()
    // Save current messages to current session entry
    const updated = sessionEntries.map((s) =>
      s.id === activeSessionId ? { ...s, cachedMessages: messages, isActive: false } : s
    )
    // Create new session
    const newId = `session-${Date.now()}`
    const newEntry: SessionEntry = {
      id: newId,
      label: '新对话',
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
    set({
      sessionEntries: updated,
      activeSessionId: id,
      messages: target?.cachedMessages ?? [],
      isTyping: false,
      cancelledStreamId: null,
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
