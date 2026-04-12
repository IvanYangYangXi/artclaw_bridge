// Ref: docs/ui/ui-design.md#Tools
// Tool manager page: tabs, search, tool cards, batch actions, creator panel
import { useEffect, useCallback } from 'react'
import { Loader2, Star } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TabBar from '../../components/common/TabBar'
import SearchBar from '../../components/common/SearchBar'
import ToolCard from '../../components/Tools/ToolCard'
import ToolCreatorPanel from '../../components/Tools/ToolCreatorPanel'
import ToolsBatchActionBar from '../../components/Tools/ToolsBatchActionBar'
import { useToolsStore } from '../../stores/toolsStore'
import { useChatStore } from '../../stores/chatStore'
import { useAppStore } from '../../stores/appStore'
import { cn } from '../../utils/cn'
import type { ToolTab, ToolItemExtended } from '../../types'

const TABS: { key: ToolTab; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'official', label: '官方工具' },
  { key: 'marketplace', label: '市集工具' },
  { key: 'mine', label: '我的工具' },
  { key: 'create', label: '创建工具' },
]

const DCC_OPTIONS = [
  { id: '', label_zh: '全部 DCC', label_en: 'All DCCs' },
  { id: 'general', label_zh: '通用', label_en: 'General' },
  { id: 'ue57', label_zh: 'UE5', label_en: 'UE5' },
  { id: 'maya2024', label_zh: 'Maya', label_en: 'Maya' },
  { id: 'max2024', label_zh: '3ds Max', label_en: '3ds Max' },
  { id: 'blender', label_zh: 'Blender', label_en: 'Blender' },
  { id: 'houdini', label_zh: 'Houdini', label_en: 'Houdini' },
  { id: 'sp', label_zh: 'SP', label_en: 'SP' },
  { id: 'sd', label_zh: 'SD', label_en: 'SD' },
  { id: 'comfyui', label_zh: 'ComfyUI', label_en: 'ComfyUI' },
]

export default function ToolsPage() {
  const {
    loading,
    activeTab,
    searchQuery,
    dccFilter,
    favoritesOnly,
    setActiveTab,
    setSearchQuery,
    setDCCFilter,
    setFavoritesOnly,
    filteredTools,
    fetchToolsList,
    doPin,
  } = useToolsStore()

  const language = useAppStore((s) => s.language)

  const navigate = useNavigate()
  const tools = filteredTools()

  // Fetch from API on mount
  useEffect(() => {
    fetchToolsList()
  }, [fetchToolsList])

  // Handle run: navigate to chat with execution context (right panel shows param form)
  const handleRun = useCallback(
    (tool: ToolItemExtended) => {
      const { setExecutionContext, setPrefill } = useChatStore.getState()
      
      // Pin the tool first
      doPin(tool.id)
      
      // Build parameters from tool manifest inputs
      const params = (tool.manifest?.inputs ?? []).map((inp) => ({
        id: inp.id,
        name: inp.name,
        type: inp.type as 'string' | 'number' | 'boolean' | 'enum' | 'image',
        required: inp.required,
        default: inp.default,
        min: inp.min,
        max: inp.max,
        step: inp.step,
        options: inp.options,
        description: inp.description,
      }))
      const defaults: Record<string, unknown> = {}
      for (const p of params) {
        if (p.default !== undefined) defaults[p.id] = p.default
      }
      
      // Determine if AI is needed
      let needsAI = false
      if (tool.implementationType === 'skill_wrapper') {
        needsAI = true
      } else if (tool.implementationType === 'composite') {
        // Check if composite contains skill references
        const tools = tool.manifest?.implementation?.tools ?? []
        needsAI = tools.some((toolRef: string) => toolRef.startsWith('skill:'))
      } else if (tool.implementationType === 'script') {
        needsAI = false
      }
      
      setExecutionContext({
        type: 'tool',
        id: tool.id,
        name: tool.name,
        parameters: params,
        values: defaults,
        needsAI,
      })
      
      // Set prefill message
      setPrefill(
        `请帮我运行工具 "${tool.name}"`,
        `配置工具 "${tool.name}" 的参数`
      )
      
      navigate('/')
    },
    [navigate, doPin],
  )

  // Handle edit: navigate to chat with prefill
  const handleEdit = useCallback(
    (tool: ToolItemExtended) => {
      const { setPrefill } = useChatStore.getState()
      setPrefill(
        `/edit tool:${tool.id}`,
        `即将编辑工具 "${tool.name}"`,
      )
      navigate('/')
    },
    [navigate],
  )

  // Handle creator method selection
  const handleCreateMethod = useCallback(
    (method: 'skill_wrapper' | 'script' | 'composite') => {
      const { setPrefill } = useChatStore.getState()
      setPrefill(
        `/create tool --method ${method}`,
        `即将创建工具`,
      )
      navigate('/')
    },
    [navigate],
  )

  const filterSelectClass = 'px-2 py-1.5 rounded text-xs bg-gray-800 text-gray-300 border border-gray-600 focus:border-blue-500 focus:outline-none'

  return (
    <div className="flex flex-col h-full bg-bg-primary">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-border-default bg-bg-secondary">
        <h1 className="text-title text-text-primary mb-3">工具管理器</h1>
        <div className="flex items-center gap-3 flex-wrap">
          <TabBar tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

          {activeTab !== 'create' && (
            <>
              {/* DCC filter */}
              <select
                value={dccFilter}
                onChange={(e) => setDCCFilter(e.target.value)}
                className={filterSelectClass}
              >
                {DCC_OPTIONS.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {language === 'zh' ? opt.label_zh : opt.label_en}
                  </option>
                ))}
              </select>

              {/* Favorites filter */}
              <button
                onClick={() => setFavoritesOnly(!favoritesOnly)}
                className={cn(
                  'flex items-center gap-1 px-2 py-1.5 rounded text-xs border transition-colors',
                  favoritesOnly
                    ? 'bg-yellow-600/20 text-yellow-300 border-yellow-500'
                    : 'bg-gray-800 text-gray-300 border-gray-600 hover:border-gray-500'
                )}
              >
                <Star className={cn('w-3 h-3', favoritesOnly && 'fill-current')} />
                {language === 'zh' ? '收藏' : 'Favorites'}
              </button>
            </>
          )}

          <div className="flex-1" />
          {activeTab !== 'create' && (
            <SearchBar
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder={language === 'zh' ? '搜索工具...' : 'Search tools...'}
              className="w-64"
            />
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {activeTab === 'create' ? (
          <ToolCreatorPanel onSelectMethod={handleCreateMethod} />
        ) : (
          <>
            <ToolsBatchActionBar />

            {loading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="w-6 h-6 animate-spin text-text-dim" />
                <span className="ml-2 text-body text-text-dim">加载中...</span>
              </div>
            ) : tools.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-text-dim">
                <p className="text-body">暂无工具</p>
                {searchQuery && (
                  <p className="text-small mt-1">
                    未找到匹配 &quot;{searchQuery}&quot; 的结果
                  </p>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {tools.map((tool) => (
                  <ToolCard
                    key={tool.id}
                    tool={tool}
                    onRun={handleRun}
                    onEdit={handleEdit}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer stats */}
      {activeTab !== 'create' && (
        <div className="shrink-0 px-6 py-2 border-t border-border-default text-[11px] text-text-dim">
          共 {tools.length} 个工具
        </div>
      )}
    </div>
  )
}
