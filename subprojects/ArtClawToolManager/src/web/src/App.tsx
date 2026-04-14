// Ref: docs/specs/architecture-design.md#Pages
// Root app with React Router
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import ChatPage from './pages/Chat'
import SkillsPage from './pages/Skills'
import WorkflowsPage from './pages/Workflows'
import ToolsPage from './pages/Tools'
import SettingsPage from './pages/Settings'
import { useAppStore } from './stores/appStore'
import { useChatStore } from './stores/chatStore'

function AppInit() {
  const fetchDCCOptions = useAppStore((s) => s.fetchDCCOptions)
  const fetchAgents = useAppStore((s) => s.fetchAgents)
  const connect = useChatStore((s) => s.connect)
  const activeSessionId = useChatStore((s) => s.activeSessionId)

  useEffect(() => {
    // Fetch DCC options and agents from backend
    fetchDCCOptions()
    fetchAgents()
  }, [fetchDCCOptions, fetchAgents])

  // Re-connect WebSocket whenever active session changes
  useEffect(() => {
    const wsUrl = `ws://${window.location.host}/ws/chat/${activeSessionId}`
    connect(wsUrl)
  }, [activeSessionId, connect])

  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <AppInit />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/skills" element={<SkillsPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/tools" element={<ToolsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
