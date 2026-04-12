// Ref: docs/ui/ui-design.md#Layout
// Main layout: Sidebar + Content area + optional Right panel
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import RightPanel from './RightPanel'

export default function Layout() {
  const location = useLocation()
  const showRightPanel = location.pathname === '/'

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Content area */}
      <main className="flex-1 min-w-0 overflow-hidden">
        <Outlet />
      </main>

      {/* Right panel (only on Chat page) */}
      {showRightPanel && <RightPanel />}
    </div>
  )
}
