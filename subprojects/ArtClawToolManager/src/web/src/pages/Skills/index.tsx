// Ref: docs/ui/ui-design.md#Skills
// Skills management page: filters, tabs, search, skill cards, batch actions
import { useEffect, useState, useMemo } from 'react'
import { Loader2, Clock, Star } from 'lucide-react'
import TabBar from '../../components/common/TabBar'
import SearchBar from '../../components/common/SearchBar'
import SkillCard from '../../components/Skills/SkillCard'
import BatchActionBar from '../../components/Skills/BatchActionBar'
import { useSkillsStore } from '../../stores/skillsStore'
import { useAppStore } from '../../stores/appStore'
import { fetchRecentSkills } from '../../api/client'
import { DCC_DISPLAY_NAMES } from '../../constants/dccTypes'
import { cn } from '../../utils/cn'
import type { SkillTab } from '../../types'

const TABS_ZH: { key: SkillTab; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'official', label: '官方' },
  { key: 'marketplace', label: '市集' },
  { key: 'platform', label: '平台' },
]

const TABS_EN: { key: SkillTab; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'official', label: 'Official' },
  { key: 'marketplace', label: 'Marketplace' },
  { key: 'platform', label: 'Platform' },
]

const STATUS_OPTIONS = [
  { id: '', label_zh: '全部状态', label_en: 'All Status' },
  { id: 'installed', label_zh: '已安装', label_en: 'Installed' },
  { id: 'not_installed', label_zh: '未安装', label_en: 'Not Installed' },
  { id: 'disabled', label_zh: '已禁用', label_en: 'Disabled' },
  { id: 'update_available', label_zh: '有更新', label_en: 'Update Available' },
  { id: 'pending_publish', label_zh: '待发布', label_en: 'Pending Publish' },
  { id: 'no_source', label_zh: '无源码', label_en: 'No Source' },
]

interface RecentSkillItem {
  id: string
  name: string
  type: string
  lastUsedAgo: string
}

const MOCK_RECENT_SKILLS: RecentSkillItem[] = [
  { id: '1', name: 'comfyui-txt2img', type: 'Skill', lastUsedAgo: '3 分钟前' },
  { id: '2', name: 'ue57-operation-rules', type: 'Skill', lastUsedAgo: '25 分钟前' },
  { id: '3', name: 'comfyui-controlnet', type: 'Skill', lastUsedAgo: '1 小时前' },
  { id: '4', name: 'blender-material-ops', type: 'Skill', lastUsedAgo: '2 小时前' },
]

export default function SkillsPage() {
  const {
    loading,
    skills: allSkills,
    activeTab,
    searchQuery,
    dccFilter,
    statusFilter,
    favoritesOnly,
    setActiveTab,
    setSearchQuery,
    setDCCFilter,
    setStatusFilter,
    setFavoritesOnly,
    filteredSkills,
    fetchSkillsList,
  } = useSkillsStore()

  const language = useAppStore((s) => s.language)
  const skills = filteredSkills()
  const tabs = language === 'zh' ? TABS_ZH : TABS_EN

  // 动态生成 DCC 选项：从所有 skills 的 targetDCCs 聚合，去重排序
  const dccOptions = useMemo(() => {
    const ids = new Set<string>()
    for (const s of allSkills) {
      for (const d of s.targetDCCs) {
        if (d && d !== 'general') ids.add(d)
      }
    }
    const dynamic = Array.from(ids).sort().map((id) => ({
      id,
      label_zh: DCC_DISPLAY_NAMES[id] ?? id,
      label_en: DCC_DISPLAY_NAMES[id] ?? id,
    }))
    return [
      { id: '', label_zh: '全部 DCC', label_en: 'All DCCs' },
      { id: 'general', label_zh: '通用', label_en: 'General' },
      ...dynamic,
    ]
  }, [allSkills])

  const [recentSkills, setRecentSkills] = useState<RecentSkillItem[]>(MOCK_RECENT_SKILLS)

  useEffect(() => {
    fetchSkillsList()
  }, [fetchSkillsList])

  useEffect(() => {
    const loadRecent = async () => {
      try {
        const res = await fetchRecentSkills(6)
        if (res.success && Array.isArray(res.data) && res.data.length > 0) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          setRecentSkills((res.data as any[]).map((r) => ({
            id: r.id as string,
            name: r.name as string,
            type: (r.type as string) ?? 'Skill',
            lastUsedAgo: (r.last_used_ago as string) ?? '',
          })))
        }
      } catch {
        // Keep mock data
      }
    }
    loadRecent()
  }, [])

  const filterSelectClass = 'px-2 py-1.5 rounded text-xs bg-gray-800 text-gray-300 border border-gray-600 focus:border-blue-500 focus:outline-none'

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-gray-700 bg-gray-800/50">
        <h1 className="text-lg font-semibold text-gray-100 mb-3">Skills</h1>
        <div className="flex items-center gap-3 flex-wrap">
          <TabBar tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

          {/* DCC filter */}
          <select
            value={dccFilter}
            onChange={(e) => setDCCFilter(e.target.value)}
            className={filterSelectClass}
          >
            {dccOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {language === 'zh' ? opt.label_zh : opt.label_en}
              </option>
            ))}
          </select>

          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className={filterSelectClass}
          >
            {STATUS_OPTIONS.map((opt) => (
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

          <div className="flex-1" />
          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder={language === 'zh' ? '搜索 Skills...' : 'Search Skills...'}
            className="w-64"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {/* Recent skills section */}
        {recentSkills.length > 0 && !searchQuery && (
          <div className="mb-5">
            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-4 h-4 text-gray-500" />
              <span className="text-xs font-medium text-gray-400">
                {language === 'zh' ? '最近使用' : 'Recent'}
              </span>
            </div>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {recentSkills.map((item) => (
                <div
                  key={item.id}
                  className={cn(
                    'shrink-0 px-4 py-2.5 rounded-lg border border-gray-700 bg-gray-800',
                    'hover:border-gray-500 cursor-pointer transition-colors min-w-[160px]',
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-200 truncate">{item.name}</span>
                    <span className="text-[10px] text-blue-400 shrink-0">{item.type}</span>
                  </div>
                  <span className="text-[11px] text-gray-500">{item.lastUsedAgo}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <BatchActionBar />

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-gray-500" />
            <span className="ml-2 text-sm text-gray-500">
              {language === 'zh' ? '加载中...' : 'Loading...'}
            </span>
          </div>
        ) : skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-500">
            <p className="text-sm">{language === 'zh' ? '暂无 Skills' : 'No Skills'}</p>
            {searchQuery && (
              <p className="text-xs mt-1">
                {language === 'zh'
                  ? `未找到匹配 "${searchQuery}" 的结果`
                  : `No results matching "${searchQuery}"`}
              </p>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {skills.map((skill) => (
              <SkillCard key={skill.id} skill={skill} />
            ))}
          </div>
        )}
      </div>

      {/* Footer stats */}
      <div className="shrink-0 px-6 py-2 border-t border-gray-700 text-[11px] text-gray-500">
        {language === 'zh' ? `共 ${skills.length} 个 Skills` : `${skills.length} Skills total`}
      </div>
    </div>
  )
}
