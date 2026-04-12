// Ref: docs/ui/ui-design.md#Workflows
// Workflow library page: tabs, search, view modes, workflow cards
import { useEffect } from 'react'
import { Loader2, LayoutGrid, LayoutList, Star, Download, Play, Image } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import TabBar from '../../components/common/TabBar'
import SearchBar from '../../components/common/SearchBar'
import WorkflowCard from '../../components/Workflows/WorkflowCard'
import { useWorkflowsStore } from '../../stores/workflowsStore'
import { cn } from '../../utils/cn'
import type { WorkflowTab, WorkflowItem } from '../../types'

const TABS: { key: WorkflowTab; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'official', label: '官方' },
  { key: 'marketplace', label: '市集' },
  { key: 'mine', label: '我的' },
]

export default function WorkflowsPage() {
  const {
    loading,
    activeTab,
    searchQuery,
    viewMode,
    favoritesOnly,
    setActiveTab,
    setSearchQuery,
    setViewMode,
    setFavoritesOnly,
    filteredWorkflows,
    fetchWorkflowsList,
  } = useWorkflowsStore()

  const workflows = filteredWorkflows()

  useEffect(() => {
    fetchWorkflowsList()
  }, [fetchWorkflowsList])

  return (
    <div className="flex flex-col h-full bg-bg-primary">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-border-default bg-bg-secondary">
        <h1 className="text-title text-text-primary mb-3">Workflow 库</h1>
        <div className="flex items-center gap-4">
          <TabBar tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                'p-1.5 rounded transition-colors',
                viewMode === 'grid'
                  ? 'bg-accent/20 text-accent'
                  : 'text-text-dim hover:bg-bg-tertiary hover:text-text-primary',
              )}
              title="网格视图"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'p-1.5 rounded transition-colors',
                viewMode === 'list'
                  ? 'bg-accent/20 text-accent'
                  : 'text-text-dim hover:bg-bg-tertiary hover:text-text-primary',
              )}
              title="列表视图"
            >
              <LayoutList className="w-4 h-4" />
            </button>
          </div>

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
            收藏
          </button>

          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="搜索 Workflows..."
            className="w-64"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-text-dim" />
            <span className="ml-2 text-body text-text-dim">加载中...</span>
          </div>
        ) : workflows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-text-dim">
            <Image className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-body">暂无 Workflows</p>
            {searchQuery && (
              <p className="text-small mt-1">
                未找到匹配 &quot;{searchQuery}&quot; 的结果
              </p>
            )}
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {workflows.map((wf) => (
              <WorkflowCard key={wf.id} workflow={wf} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {workflows.map((wf) => (
              <WorkflowListRow key={wf.id} workflow={wf} />
            ))}
          </div>
        )}
      </div>

      {/* Footer stats */}
      <div className="shrink-0 px-6 py-2 border-t border-border-default text-[11px] text-text-dim">
        共 {workflows.length} 个 Workflows
      </div>
    </div>
  )
}

// ---------- List view row ----------

function WorkflowListRow({ workflow }: { workflow: WorkflowItem }) {
  const navigate = useNavigate()

  return (
    <div
      className={cn(
        'flex items-center gap-4 px-4 py-3 rounded-lg border',
        'border-border-default bg-bg-secondary hover:border-border-hover transition-colors',
      )}
    >
      {/* Thumbnail */}
      <div className="w-16 h-16 rounded bg-bg-tertiary flex items-center justify-center shrink-0 overflow-hidden">
        {workflow.previewImage ? (
          <img src={workflow.previewImage} alt={workflow.name} className="w-full h-full object-cover" />
        ) : (
          <Image className="w-6 h-6 text-text-dim opacity-30" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-body font-medium text-text-primary truncate">{workflow.name}</span>
          {workflow.version && (
            <span className="text-[11px] text-text-dim shrink-0">v{workflow.version}</span>
          )}
        </div>
        <p className="text-small text-text-secondary truncate">{workflow.description}</p>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-3 text-[11px] text-text-dim shrink-0">
        {workflow.stats.rating > 0 && (
          <span className="flex items-center gap-0.5">
            <Star className="w-3 h-3 fill-warning text-warning" />
            {workflow.stats.rating}
          </span>
        )}
        {workflow.stats.downloads > 0 && (
          <span className="flex items-center gap-0.5">
            <Download className="w-3 h-3" />
            {workflow.stats.downloads >= 1000
              ? `${(workflow.stats.downloads / 1000).toFixed(1)}k`
              : workflow.stats.downloads}
          </span>
        )}
      </div>

      {/* Run */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-1 px-3 py-1.5 rounded text-[12px] bg-accent/20 text-accent hover:bg-accent/30 transition-colors shrink-0"
      >
        <Play className="w-3.5 h-3.5" />
        <span>运行</span>
      </button>
    </div>
  )
}
