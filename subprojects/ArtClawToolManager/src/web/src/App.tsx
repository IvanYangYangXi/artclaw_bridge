import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <div className="min-h-screen bg-gray-100">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto py-6 px-4">
            <h1 className="text-3xl font-bold text-gray-900">
              🔧 ArtClaw Tool Manager
            </h1>
            <p className="mt-2 text-gray-600">
              统一工具管理器 - 整合 Skill、Workflow、工具管理
            </p>
          </div>
        </header>
        
        <main className="max-w-7xl mx-auto py-6 px-4">
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">欢迎使用</h2>
            <p className="text-gray-600 mb-4">
              这是一个占位页面。完整的 UI 正在开发中。
            </p>
            
            <div className="grid grid-cols-3 gap-4 mt-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="font-medium text-blue-900">🎯 Skills</h3>
                <p className="text-sm text-blue-700 mt-1">管理 AI Skills</p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="font-medium text-green-900">📋 Workflows</h3>
                <p className="text-sm text-green-700 mt-1">Workflow 模板库</p>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <h3 className="font-medium text-purple-900">🔧 Tools</h3>
                <p className="text-sm text-purple-700 mt-1">工具管理器</p>
              </div>
            </div>
            
            <div className="mt-6">
              <button 
                onClick={() => setCount(c => c + 1)}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
              >
                点击次数: {count}
              </button>
            </div>
          </div>
        </main>
      </div>
    </>
  )
}

export default App
